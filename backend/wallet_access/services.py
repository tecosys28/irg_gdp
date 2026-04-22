"""
IRG Chain 888101 — Wallet access business logic.

All write operations go through functions in this module. Views are thin
REST wrappers around these functions so that management commands, Celery
tasks, and tests can share the same code paths.

Security invariants enforced here:
  * The wallet encryption password is verified against its PBKDF2 hash;
    the server never sees plaintext beyond that verification step.
  * The 15-word seed phrase is hashed on arrival and only the hash is
    retained; plaintext is discarded before the function returns.
  * State transitions happen inside DB transactions so crashes cannot
    leave a wallet half-activated or half-recovered.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable, List, Optional

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import (
    InactivityEvent,
    NomineeRegistration,
    NomineeSignature,
    OwnershipTransferCase,
    RecoveryCase,
    WalletActivation,
    WalletDevice,
)
from .notifications import notify

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# EXCEPTIONS
# ─────────────────────────────────────────────────────────────────────────────

class WalletAccessError(Exception):
    """Base class so views can catch one and return structured errors."""
    code = 'wallet_access_error'


class WalletNotFound(WalletAccessError):
    code = 'wallet_not_found'


class WalletAlreadyActivated(WalletAccessError):
    code = 'wallet_already_activated'


class InvalidSeedPhrase(WalletAccessError):
    code = 'invalid_seed_phrase'


class InvalidPassword(WalletAccessError):
    code = 'invalid_password'


class PasswordPolicyViolation(WalletAccessError):
    code = 'password_policy'


class NomineePolicyViolation(WalletAccessError):
    code = 'nominee_policy'


class DeviceCoolingOff(WalletAccessError):
    code = 'device_cooling_off'


class WalletLocked(WalletAccessError):
    code = 'wallet_locked'


class WalletNotTransactable(WalletAccessError):
    code = 'wallet_not_transactable'


class RecoveryError(WalletAccessError):
    code = 'recovery_error'


# ─────────────────────────────────────────────────────────────────────────────
# POLICY
# ─────────────────────────────────────────────────────────────────────────────

WALLET_PASSWORD_MIN_LEN = 8
WALLET_PASSWORD_ITERATIONS = 600_000   # OWASP 2024 PBKDF2-SHA256 recommendation
SEED_PHRASE_WORD_COUNT = 15
MAX_FAILED_PASSWORD_ATTEMPTS = 10
LOCK_DURATION = timedelta(hours=24)
DEVICE_COOLING_OFF = timedelta(hours=48)
SOCIAL_RECOVERY_COOLING_OFF = timedelta(days=7)
TRUSTEE_PUBLIC_NOTICE = timedelta(days=30)
OWNERSHIP_TRANSFER_NOTICE = timedelta(days=30)
REVERSIBILITY_WINDOW = timedelta(days=90)
SOCIAL_RECOVERY_MAX_VALUE_INR = Decimal('50000')
# Activity-based inactivity watchdog.
INACTIVITY_PROMPT_AFTER = timedelta(days=365)
INACTIVITY_REMINDER_AFTER_PROMPT = timedelta(days=2)
INACTIVITY_NOMINEES_AFTER_REMINDER = timedelta(days=2)

_ALPHA_RE = re.compile(r'[A-Za-z]')
_DIGIT_RE = re.compile(r'\d')


def _validate_wallet_password(password: str, *,
                              user_login_password_hash: Optional[str] = None) -> None:
    """
    Enforce policy:
      * at least 8 characters
      * at least one letter and one digit (symbol not required)
      * OR a 4+ word passphrase of 20+ characters
      * MUST be different from the login password
    """
    if not password or len(password) < WALLET_PASSWORD_MIN_LEN:
        raise PasswordPolicyViolation(
            f'Wallet password must be at least {WALLET_PASSWORD_MIN_LEN} characters.'
        )

    is_complex = bool(_ALPHA_RE.search(password) and _DIGIT_RE.search(password))
    words = password.strip().split()
    is_passphrase = len(words) >= 4 and len(password) >= 20

    if not (is_complex or is_passphrase):
        raise PasswordPolicyViolation(
            'Wallet password must contain a letter and a digit, '
            'OR be a 4+ word passphrase of 20+ characters.'
        )

    if user_login_password_hash:
        if check_password(password, user_login_password_hash):
            raise PasswordPolicyViolation(
                'Your wallet password must be different from your login password.'
            )


def _hash_wallet_password(password: str) -> tuple[str, str]:
    """Return (hash, salt). Uses Django's PBKDF2 hasher at our iteration count."""
    salt = secrets.token_hex(16)
    hashed = make_password(password, salt=salt, hasher='pbkdf2_sha256')
    return hashed, salt


def _hash_seed_phrase(words: Iterable[str]) -> str:
    joined = ' '.join(w.strip().lower() for w in words)
    return '0x' + hashlib.sha256(joined.encode('utf-8')).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# WALLET INFO (read)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WalletInfo:
    address: str
    chain_id: int
    state: str
    state_label: str
    blocking_reason: str
    holder_type: str
    legal_entity_name: str
    entity_type: str
    created_at: str
    activated_at: Optional[str]
    nominee_count: int
    nominee_shares_total: str
    active_device_count: int
    failed_password_attempts: int
    locked_until: Optional[str]
    last_activity_at: Optional[str]
    is_transactable: bool


def get_wallet_info(user) -> WalletInfo:
    wallet = getattr(user, 'wallet_activation', None)
    if wallet is None:
        raise WalletNotFound('No wallet found for this user.')

    nominees = wallet.nominees.filter(active=True)
    total = sum((n.share_percent for n in nominees), Decimal('0'))
    return WalletInfo(
        address=wallet.wallet_address,
        chain_id=888101,
        state=wallet.state,
        state_label=wallet.get_state_display(),
        blocking_reason=wallet.blocking_reason,
        holder_type=wallet.holder_type,
        legal_entity_name=wallet.legal_entity_name,
        entity_type=wallet.entity_type,
        created_at=wallet.created_at.isoformat(),
        activated_at=wallet.activated_at.isoformat() if wallet.activated_at else None,
        nominee_count=nominees.count(),
        nominee_shares_total=str(total),
        active_device_count=wallet.devices.filter(state='ACTIVE').count(),
        failed_password_attempts=wallet.failed_password_attempts,
        locked_until=wallet.locked_until.isoformat() if wallet.locked_until else None,
        last_activity_at=wallet.last_activity_at.isoformat() if wallet.last_activity_at else None,
        is_transactable=wallet.is_transactable,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACTIVATION
# ─────────────────────────────────────────────────────────────────────────────

@db_transaction.atomic
def activate_wallet(
    user,
    *,
    wallet_password: str,
    seed_phrase_words: list[str],
    holder_type: str,
    nominees: List[dict],
    device_id_hash: str,
    device_label: str = '',
    platform: str = '',
    terms_accepted: bool = False,
    # Legal-person only (ignored when holder_type == 'INDIVIDUAL').
    legal_entity_name: str = '',
    entity_type: str = '',
) -> WalletInfo:
    """
    Complete activation in one atomic step.

    nominees: list of dicts with keys name, relationship, email, mobile,
              share_percent, id_document_hash (optional), social_recovery_threshold.
              REQUIRED for individual wallets. For legal-person wallets the
              list is optional — the legal entity itself is effectively its
              own successor and recovery always runs through the trustee /
              Ombudsman path.
    """
    if not terms_accepted:
        raise WalletAccessError('You must accept the recovery terms to activate.')

    wallet = getattr(user, 'wallet_activation', None)
    if wallet is None:
        raise WalletNotFound('No wallet found. Complete registration first.')
    if wallet.state == 'ACTIVATED':
        raise WalletAlreadyActivated('Wallet is already activated.')
    if wallet.state in ('SUSPENDED', 'RECOVERED'):
        raise WalletAccessError(f'Wallet is {wallet.state}. Activation not permitted.')

    # 1. Password
    _validate_wallet_password(wallet_password, user_login_password_hash=user.password)
    pw_hash, salt = _hash_wallet_password(wallet_password)

    # 2. Seed phrase
    words = [w.strip().lower() for w in (seed_phrase_words or []) if w and w.strip()]
    if len(words) != SEED_PHRASE_WORD_COUNT:
        raise InvalidSeedPhrase(
            f'Seed phrase must be exactly {SEED_PHRASE_WORD_COUNT} words.'
        )
    seed_hash = _hash_seed_phrase(words)

    # 3. Holder type
    valid_holder_types = {c for c, _ in WalletActivation.HOLDER_TYPE_CHOICES}
    if holder_type not in valid_holder_types:
        raise WalletAccessError('Invalid holder_type.')
    if holder_type == 'LEGAL_PERSON':
        if not legal_entity_name:
            raise WalletAccessError('legal_entity_name is required for legal-person wallets.')
        valid_entity_types = {c for c, _ in WalletActivation.ENTITY_TYPE_CHOICES if c}
        if entity_type and entity_type not in valid_entity_types:
            raise WalletAccessError('Invalid entity_type.')

    # 4. Nominees — required for individuals only. Legal persons are
    # allowed (and encouraged) to skip; in their case the entity itself
    # is effectively its own nominee and recovery goes via trustee path.
    if holder_type == 'INDIVIDUAL':
        if not nominees or len(nominees) < 2:
            raise NomineePolicyViolation('At least two nominees are required for individual wallets.')
        share_total = Decimal('0')
        for n in nominees:
            share = Decimal(str(n.get('share_percent', 0)))
            if share <= 0:
                raise NomineePolicyViolation('Every nominee must have a positive share.')
            share_total += share
        if share_total != Decimal('100'):
            raise NomineePolicyViolation(
                f'Nominee shares must total 100% (got {share_total}).'
            )
    else:
        # Legal person — nominees optional; if provided, still validate share sum.
        if nominees:
            share_total = sum((Decimal(str(n.get('share_percent', 0))) for n in nominees), Decimal('0'))
            if share_total != Decimal('100'):
                raise NomineePolicyViolation(
                    f'If nominees are provided, shares must total 100% (got {share_total}).'
                )

    # 5. Device binding — first activation waives cooling-off.
    WalletDevice.objects.create(
        wallet=wallet,
        device_id_hash=device_id_hash,
        device_label=device_label[:100],
        platform=platform[:20],
        state='ACTIVE',
        cooling_off_until=None,
        activated_at=timezone.now(),
    )

    # 6. Persist nominees (if any)
    for n in (nominees or []):
        NomineeRegistration.objects.create(
            wallet=wallet,
            name=n.get('name', '')[:200],
            relationship=n.get('relationship', '')[:60],
            email=n.get('email', '')[:254],
            mobile=n.get('mobile', '')[:20],
            id_document_hash=n.get('id_document_hash', '')[:66],
            share_percent=Decimal(str(n['share_percent'])),
            social_recovery_threshold=int(n.get('social_recovery_threshold', 2)),
            active=True,
        )

    # 7. Flip the wallet to ACTIVATED
    wallet.password_hash = pw_hash
    wallet.password_salt = salt
    wallet.password_algo = 'pbkdf2_sha256'
    wallet.password_iterations = WALLET_PASSWORD_ITERATIONS
    wallet.seed_phrase_hash = seed_hash
    wallet.seed_phrase_confirmed = True
    wallet.seed_phrase_confirmed_at = timezone.now()
    wallet.holder_type = holder_type
    wallet.legal_entity_name = legal_entity_name[:200] if holder_type == 'LEGAL_PERSON' else ''
    wallet.entity_type = entity_type[:24] if holder_type == 'LEGAL_PERSON' else ''
    wallet.state = 'ACTIVATED'
    wallet.activated_at = timezone.now()
    wallet.last_activity_at = timezone.now()
    wallet.failed_password_attempts = 0
    wallet.locked_until = None
    wallet.save()

    # 8. Notifications
    db_transaction.on_commit(lambda: notify(user, 'wallet.activated', {
        'wallet_address': wallet.wallet_address,
    }))
    for n in wallet.nominees.filter(active=True):
        db_transaction.on_commit(lambda n=n: notify(
            {'email': n.email, 'mobile': n.mobile, 'name': n.name},
            'nominee.registered',
            {
                'nominee_name': n.name,
                'nominator_name': user.get_full_name() or user.email,
            },
        ))

    # 9. Defensive overwrite of plaintext secrets in this stack frame.
    wallet_password = '***'          # noqa: F841
    seed_phrase_words = None         # noqa: F841
    words = None                     # noqa: F841

    return get_wallet_info(user)


# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD CHANGE
# ─────────────────────────────────────────────────────────────────────────────

@db_transaction.atomic
def change_wallet_password(user, *, old_password: str, new_password: str) -> None:
    wallet = _require_wallet(user)
    if wallet.state != 'ACTIVATED':
        raise WalletNotTransactable(wallet.blocking_reason)

    if not check_password(old_password, wallet.password_hash):
        _register_failed_password_attempt(wallet)
        raise InvalidPassword('Current wallet password is incorrect.')

    _validate_wallet_password(new_password, user_login_password_hash=user.password)
    pw_hash, salt = _hash_wallet_password(new_password)
    wallet.password_hash = pw_hash
    wallet.password_salt = salt
    wallet.failed_password_attempts = 0
    wallet.locked_until = None
    wallet.save(update_fields=['password_hash', 'password_salt',
                               'failed_password_attempts', 'locked_until',
                               'last_state_change'])

    db_transaction.on_commit(lambda: notify(user, 'wallet.unusual_activity', {
        'wallet_address': wallet.wallet_address,
        'description': 'Your wallet password was changed.',
    }))


def verify_wallet_password(user, password: str) -> bool:
    """
    Used by the transaction sign path to confirm the user knows their
    wallet password before the device decrypts the private key locally.
    """
    wallet = _require_wallet(user)
    if wallet.state == 'LOCKED':
        if wallet.locked_until and wallet.locked_until > timezone.now():
            raise WalletLocked(wallet.blocking_reason)
        # Auto-unlock after the lock window expires
        wallet.state = 'ACTIVATED' if wallet.password_hash else 'CREATED'
        wallet.locked_until = None
        wallet.failed_password_attempts = 0
        wallet.save()

    if not wallet.password_hash:
        raise WalletNotTransactable('Wallet has not been activated.')

    if check_password(password, wallet.password_hash):
        if wallet.failed_password_attempts:
            wallet.failed_password_attempts = 0
            wallet.save(update_fields=['failed_password_attempts', 'last_state_change'])
        return True

    _register_failed_password_attempt(wallet)
    return False


def _register_failed_password_attempt(wallet: WalletActivation) -> None:
    wallet.failed_password_attempts += 1
    if wallet.failed_password_attempts >= MAX_FAILED_PASSWORD_ATTEMPTS:
        wallet.state = 'LOCKED'
        wallet.locked_until = timezone.now() + LOCK_DURATION
    wallet.save(update_fields=['failed_password_attempts', 'state', 'locked_until',
                               'last_state_change'])


# ─────────────────────────────────────────────────────────────────────────────
# NOMINEE MANAGEMENT (post-activation)
# ─────────────────────────────────────────────────────────────────────────────

@db_transaction.atomic
def update_nominees(user, *, nominees: List[dict], wallet_password: str) -> None:
    """
    Replace the active nominee set.
    For CREATED (pre-activation) wallets: password is not required yet.
    For ACTIVATED wallets: wallet password must be re-entered (sensitive change).
    """
    wallet = _require_wallet(user)

    # Only require password verification on already-activated wallets
    if wallet.state == 'ACTIVATED':
        if not verify_wallet_password(user, wallet_password):
            raise InvalidPassword('Wallet password incorrect.')
    elif wallet.state not in ('CREATED',):
        raise WalletNotTransactable(wallet.blocking_reason or 'Wallet is not in a state that allows nominee updates.')

    if not nominees or len(nominees) < 1:
        raise NomineePolicyViolation('At least one nominee is required.')
    total = sum((Decimal(str(n['share_percent'])) for n in nominees), Decimal('0'))
    if total != Decimal('100'):
        raise NomineePolicyViolation(f'Nominee shares must total 100% (got {total}).')

    # Retire existing
    wallet.nominees.filter(active=True).update(
        active=False,
        revoked_at=timezone.now(),
        revoke_reason='Replaced by user update',
    )
    # Add new
    for n in nominees:
        NomineeRegistration.objects.create(
            wallet=wallet,
            name=n.get('name', '')[:200],
            relationship=n.get('relationship', '')[:60],
            email=n.get('email', '')[:254],
            mobile=n.get('mobile', '')[:20],
            id_document_hash=n.get('id_document_hash', '')[:66],
            share_percent=Decimal(str(n['share_percent'])),
            social_recovery_threshold=int(n.get('social_recovery_threshold', 2)),
            active=True,
        )

    db_transaction.on_commit(lambda: notify(user, 'wallet.unusual_activity', {
        'wallet_address': wallet.wallet_address,
        'description': 'Your nominee list was updated.',
    }))


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@db_transaction.atomic
def bind_new_device(user, *, device_id_hash: str, device_label: str = '',
                    platform: str = '', wallet_password: str) -> WalletDevice:
    """
    Rebind a new device. Retires the previous ACTIVE device and starts a
    cooling-off period on the new one. Used when a user gets a new phone.
    """
    wallet = _require_wallet(user)
    if wallet.state not in ('ACTIVATED', 'CREATED'):
        raise WalletNotTransactable(wallet.blocking_reason)
    if not verify_wallet_password(user, wallet_password):
        raise InvalidPassword('Wallet password incorrect.')

    # Retire old active devices
    wallet.devices.filter(state='ACTIVE').update(
        state='RETIRED',
        retired_at=timezone.now(),
    )
    # Bind new, subject to cooling-off
    device = WalletDevice.objects.create(
        wallet=wallet,
        device_id_hash=device_id_hash,
        device_label=device_label[:100],
        platform=platform[:20],
        state='ACTIVE',
        cooling_off_until=timezone.now() + DEVICE_COOLING_OFF,
    )

    db_transaction.on_commit(lambda: notify(user, 'wallet.unusual_activity', {
        'wallet_address': wallet.wallet_address,
        'description': (
            f'A new device ({device.device_label or "unnamed"}) was bound to your wallet. '
            f'It can transact after the {DEVICE_COOLING_OFF} cooling-off period.'
        ),
    }))
    return device


def revoke_device(user, device_id: int, *, wallet_password: str) -> None:
    wallet = _require_wallet(user)
    if not verify_wallet_password(user, wallet_password):
        raise InvalidPassword('Wallet password incorrect.')
    device = wallet.devices.filter(id=device_id).first()
    if not device:
        raise WalletAccessError('Device not found.')
    device.state = 'REVOKED'
    device.retired_at = timezone.now()
    device.save(update_fields=['state', 'retired_at'])


# ─────────────────────────────────────────────────────────────────────────────
# SELF-FREEZE (emergency)
# ─────────────────────────────────────────────────────────────────────────────

def emergency_freeze(user, *, reason: str) -> None:
    wallet = _require_wallet(user)
    if wallet.state in ('SUSPENDED', 'RECOVERED'):
        return
    wallet.state = 'SUSPENDED'
    wallet.save(update_fields=['state', 'last_state_change'])
    notify(user, 'wallet.unusual_activity', {
        'wallet_address': wallet.wallet_address,
        'description': f'Wallet frozen by user. Reason: {reason[:200]}',
    })


# ─────────────────────────────────────────────────────────────────────────────
# INACTIVITY WATCHDOG
# ─────────────────────────────────────────────────────────────────────────────
#
# Replaces the old calendar-based annual liveness check with an
# activity-driven clock:
#
#   1. `touch_activity()` is called on login, on every transaction
#      submission, and on explicit confirmation — so an engaged user is
#      never pestered.
#   2. A nightly sweep checks wallets that have been quiet for >= 1 year:
#      * sends a "we haven't seen you" prompt
#      * 2 days later, a reminder if still quiet
#      * 2 days after THAT, nominees are alerted
#   3. Any activity (login, tx, confirmation) resets the clock.

def touch_activity(user) -> None:
    """Record user activity against their wallet. Safe no-op if no wallet."""
    wallet = getattr(user, 'wallet_activation', None)
    if wallet is None:
        return
    wallet.touch_activity()


def confirm_liveness(user):
    """
    The user explicitly taps "I am still here" in response to an inactivity
    prompt. Records the confirmation in the audit trail and resets the
    inactivity clock.
    """
    wallet = _require_wallet(user)
    wallet.touch_activity()
    return InactivityEvent.objects.create(
        wallet=wallet, kind='CONFIRMED',
        detail='User confirmed active status.',
    )


def sweep_inactivity() -> dict:
    """
    Called by a daily cron / Celery beat task. Three escalation stages:
      stage 1 — wallets quiet for >= INACTIVITY_PROMPT_AFTER that have not
                yet been prompted this round -> send prompt
      stage 2 — prompt sent >= INACTIVITY_REMINDER_AFTER_PROMPT ago,
                still no activity -> send reminder
      stage 3 — reminder sent >= INACTIVITY_NOMINEES_AFTER_REMINDER ago,
                still no activity -> alert nominees
    """
    now = timezone.now()
    stats = {'prompted': 0, 'reminded': 0, 'nominees_alerted': 0}

    active_wallets = WalletActivation.objects.filter(state='ACTIVATED')
    for wallet in active_wallets:
        last = wallet.last_activity_at or wallet.activated_at or wallet.created_at
        if not last:
            continue
        silent_for = now - last

        # Stage 3 — nominees alerted
        if (wallet.inactivity_reminder_sent_at
                and not wallet.nominees_alerted_at
                and (now - wallet.inactivity_reminder_sent_at) >= INACTIVITY_NOMINEES_AFTER_REMINDER):
            _alert_nominees_on_inactivity(wallet)
            wallet.nominees_alerted_at = now
            wallet.save(update_fields=['nominees_alerted_at', 'last_state_change'])
            InactivityEvent.objects.create(
                wallet=wallet, kind='NOMINEES_ALERTED',
                detail=f'Silent since {last.isoformat()}'
            )
            stats['nominees_alerted'] += 1
            continue

        # Stage 2 — reminder
        if (wallet.inactivity_prompt_sent_at
                and not wallet.inactivity_reminder_sent_at
                and (now - wallet.inactivity_prompt_sent_at) >= INACTIVITY_REMINDER_AFTER_PROMPT):
            notify(wallet.user, 'wallet.inactivity_reminder', {
                'wallet_address': wallet.wallet_address,
            })
            wallet.inactivity_reminder_sent_at = now
            wallet.save(update_fields=['inactivity_reminder_sent_at', 'last_state_change'])
            InactivityEvent.objects.create(
                wallet=wallet, kind='REMINDER_SENT',
                detail='Reminder after no response to inactivity prompt.',
            )
            stats['reminded'] += 1
            continue

        # Stage 1 — first prompt
        if (silent_for >= INACTIVITY_PROMPT_AFTER
                and not wallet.inactivity_prompt_sent_at):
            notify(wallet.user, 'wallet.inactivity_prompt', {
                'wallet_address': wallet.wallet_address,
                'silent_for_days': silent_for.days,
            })
            wallet.inactivity_prompt_sent_at = now
            wallet.save(update_fields=['inactivity_prompt_sent_at', 'last_state_change'])
            InactivityEvent.objects.create(
                wallet=wallet, kind='PROMPT_SENT',
                detail=f'Silent for {silent_for.days} days.',
            )
            stats['prompted'] += 1

    return stats


def _alert_nominees_on_inactivity(wallet: WalletActivation) -> None:
    for nominee in wallet.nominees.filter(active=True):
        notify(
            {'email': nominee.email, 'mobile': nominee.mobile, 'name': nominee.name},
            'wallet.inactivity_nominee_alert',
            {
                'wallet_address': wallet.wallet_address,
                'nominee_name': nominee.name,
                'nominator_name': wallet.user.get_full_name() or wallet.user.email,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# RECOVERY
# ─────────────────────────────────────────────────────────────────────────────

def _require_wallet(user) -> WalletActivation:
    wallet = getattr(user, 'wallet_activation', None)
    if wallet is None:
        raise WalletNotFound('No wallet found for this user.')
    return wallet


def initiate_self_recovery(user, *, seed_phrase_words: list[str],
                           new_device_id_hash: str,
                           new_device_label: str = '',
                           new_platform: str = '') -> RecoveryCase:
    """
    User installed the app on a fresh device, entered their 15-word seed,
    and we need to confirm + rebind.
    """
    wallet = _require_wallet(user)
    if wallet.state in ('SUSPENDED', 'RECOVERED'):
        raise WalletNotTransactable(wallet.blocking_reason)

    candidate = _hash_seed_phrase(w.strip().lower() for w in (seed_phrase_words or []))
    if candidate != wallet.seed_phrase_hash:
        raise InvalidSeedPhrase('Seed phrase does not match our records.')

    case = RecoveryCase.objects.create(
        original_wallet=wallet,
        path='SELF',
        status='APPROVED',  # self-recovery is auto-approved on seed match
        claimant_user=user,
        claimant_wallet_address=wallet.wallet_address,
        grounds='Self-recovery via seed phrase on new device.',
    )

    # Retire old devices, start cooling-off on the new one
    wallet.devices.filter(state='ACTIVE').update(
        state='RETIRED', retired_at=timezone.now()
    )
    WalletDevice.objects.create(
        wallet=wallet,
        device_id_hash=new_device_id_hash,
        device_label=new_device_label[:100],
        platform=new_platform[:20],
        state='ACTIVE',
        cooling_off_until=timezone.now() + DEVICE_COOLING_OFF,
    )

    notify(user, 'wallet.unusual_activity', {
        'wallet_address': wallet.wallet_address,
        'description': 'Self-recovery completed on a new device. Cooling-off is in effect.',
    })

    case.status = 'EXECUTED'
    case.save(update_fields=['status', 'updated_at'])
    return case


def initiate_social_recovery(*, claimant_user, original_wallet_address: str,
                             claimant_wallet_address: str,
                             grounds: str) -> RecoveryCase:
    """
    Low-value recovery filed by a nominee on behalf of the original owner
    who has lost access. Triggers cooling-off during which the original
    owner can cancel.
    """
    original = WalletActivation.objects.filter(
        wallet_address=original_wallet_address
    ).first()
    if not original:
        raise WalletNotFound('Original wallet not found.')
    if original.state in ('RECOVERED', 'SUSPENDED'):
        raise WalletNotTransactable(original.blocking_reason)

    # Verify claimant is a nominee of the original
    if not original.nominees.filter(active=True, email=claimant_user.email).exists() \
       and not original.nominees.filter(active=True, mobile=getattr(claimant_user, 'mobile', '')).exists():
        raise RecoveryError('Only a registered nominee may file social recovery.')

    now = timezone.now()
    case = RecoveryCase.objects.create(
        original_wallet=original,
        path='SOCIAL',
        status='NOTIFIED',
        claimant_user=claimant_user,
        claimant_wallet_address=claimant_wallet_address,
        grounds=grounds[:2000],
        cooling_off_ends_at=now + SOCIAL_RECOVERY_COOLING_OFF,
    )
    original.state = 'RECOVERING'
    original.save(update_fields=['state', 'last_state_change'])

    # Alarm the original owner through every channel.
    notify(original.user, 'recovery.initiated', {
        'wallet_address': original.wallet_address,
        'claimant_name': claimant_user.get_full_name() or claimant_user.email,
        'path': 'SOCIAL',
        'filed_at': now.isoformat(),
        'case_id': str(case.id),
        'cooling_off_ends_at': case.cooling_off_ends_at.isoformat(),
    })
    # Notify other nominees their signatures will be requested.
    for n in original.nominees.filter(active=True).exclude(email=claimant_user.email):
        notify(
            {'email': n.email, 'mobile': n.mobile, 'name': n.name},
            'nominee.signature_requested',
            {
                'nominee_name': n.name,
                'nominator_name': original.user.get_full_name() or original.user.email,
                'case_id': str(case.id),
            },
        )
    return case


def initiate_trustee_recovery(*, claimant_user, original_wallet_address: str,
                              claimant_wallet_address: str,
                              grounds: str, evidence_bundle_hash: str) -> RecoveryCase:
    """
    High-value or contested recovery. We file the case, emit the on-chain
    WalletRecoveryRequested event, and transition to AWAITING_OMBUDSMAN.
    The existing Ombudsman system handles the rest and emits
    OmbudsmanOrderIssued when done; our listener picks that up.
    """
    original = WalletActivation.objects.filter(
        wallet_address=original_wallet_address
    ).first()
    if not original:
        raise WalletNotFound('Original wallet not found.')
    if original.state in ('RECOVERED',):
        raise WalletNotTransactable('Wallet already recovered.')

    now = timezone.now()
    case = RecoveryCase.objects.create(
        original_wallet=original,
        path='TRUSTEE',
        status='AWAITING_OMBUDSMAN',
        claimant_user=claimant_user,
        claimant_wallet_address=claimant_wallet_address,
        grounds=grounds[:2000],
        evidence_bundle_hash=evidence_bundle_hash[:66],
        public_notice_ends_at=now + TRUSTEE_PUBLIC_NOTICE,
    )
    original.state = 'RECOVERING'
    original.save(update_fields=['state', 'last_state_change'])

    # Emit the on-chain event so the Ombudsman system can pick it up.
    try:
        from services.blockchain import BlockchainService
        svc = BlockchainService()
        tx_hash = svc.file_recovery_request(
            case_id=str(case.id),
            original_wallet=original.wallet_address,
            claimant_wallet=claimant_wallet_address or '0x' + '0' * 40,
            path='TRUSTEE',
            evidence_bundle_hash=evidence_bundle_hash,
        )
        case.recovery_requested_tx_hash = tx_hash
        case.save(update_fields=['recovery_requested_tx_hash', 'updated_at'])
    except Exception as exc:  # noqa: BLE001
        logger.error('Failed to emit WalletRecoveryRequested: %s', exc)

    # Notifications
    notify(original.user, 'recovery.initiated', {
        'wallet_address': original.wallet_address,
        'claimant_name': claimant_user.get_full_name() or claimant_user.email,
        'path': 'TRUSTEE',
        'filed_at': now.isoformat(),
        'case_id': str(case.id),
        'cooling_off_ends_at': case.public_notice_ends_at.isoformat(),
    })
    return case


def cancel_recovery(user, case_id: int, *, reason: str) -> RecoveryCase:
    """
    Original owner cancels a social or trustee recovery during cooling-off.
    """
    wallet = _require_wallet(user)
    case = RecoveryCase.objects.filter(
        id=case_id, original_wallet=wallet
    ).first()
    if not case:
        raise RecoveryError('Recovery case not found.')
    if case.status in ('EXECUTED', 'CANCELLED', 'REJECTED', 'EXPIRED'):
        raise RecoveryError(f'Case already {case.status}.')

    if case.path == 'SOCIAL' and case.cooling_off_ends_at and case.cooling_off_ends_at < timezone.now():
        raise RecoveryError('Cooling-off period has elapsed; cancellation by user no longer permitted.')

    case.status = 'CANCELLED'
    case.grounds = (case.grounds + f'\n\nCancelled by owner: {reason[:500]}').strip()
    case.save(update_fields=['status', 'grounds', 'updated_at'])

    # Restore wallet state
    wallet.state = 'ACTIVATED' if wallet.password_hash else 'CREATED'
    wallet.save(update_fields=['state', 'last_state_change'])

    # Inform the chain
    try:
        from services.blockchain import BlockchainService
        BlockchainService().cancel_recovery_request(
            case_id=str(case.id),
            original_wallet=wallet.wallet_address,
            reason=reason[:200],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('cancel_recovery_request emit failed: %s', exc)

    notify(user, 'recovery.cancelled', {
        'wallet_address': wallet.wallet_address,
        'case_id': str(case.id),
    })
    return case


def execute_ombudsman_order(*, case_id: int, order_hash: str,
                            order_tx_hash: str, disposition: str,
                            target_wallet: str) -> RecoveryCase:
    """
    Called by the event listener management command when it sees an
    OmbudsmanOrderIssued event on-chain. This is purely mechanical — the
    Ombudsman system already did the substantive decision-making.
    """
    case = RecoveryCase.objects.filter(id=case_id).first()
    if not case:
        raise RecoveryError(f'No local case {case_id} matches the Ombudsman Order.')

    case.ombudsman_order_hash = order_hash
    case.ombudsman_order_tx_hash = order_tx_hash

    if disposition == 'REJECT':
        case.status = 'REJECTED'
        case.save(update_fields=['status', 'ombudsman_order_hash',
                                 'ombudsman_order_tx_hash', 'updated_at'])
        wallet = case.original_wallet
        wallet.state = 'ACTIVATED' if wallet.password_hash else 'CREATED'
        wallet.save(update_fields=['state', 'last_state_change'])
        notify(wallet.user, 'recovery.rejected', {
            'wallet_address': wallet.wallet_address,
            'case_id': str(case.id),
            'reason': 'Ombudsman rejected the claim.',
        })
        return case

    if disposition in ('APPROVE', 'APPROVE_MODIFIED'):
        case.status = 'APPROVED'
        case.save(update_fields=['status', 'ombudsman_order_hash',
                                 'ombudsman_order_tx_hash', 'updated_at'])

        # Mechanical execution:
        # 1) Mark the old wallet RECOVERED
        # 2) The actual asset movement is performed by the governance multisig
        #    per the Order's action payload; we just record completion here.
        now = timezone.now()
        case.execution_tx_hash = order_tx_hash  # placeholder until multisig tx arrives
        case.reversibility_ends_at = now + REVERSIBILITY_WINDOW
        case.status = 'EXECUTED'
        case.save(update_fields=['status', 'execution_tx_hash',
                                 'reversibility_ends_at', 'updated_at'])
        wallet = case.original_wallet
        wallet.state = 'RECOVERED'
        wallet.save(update_fields=['state', 'last_state_change'])

        notify(wallet.user, 'recovery.executed', {
            'wallet_address': wallet.wallet_address,
            'case_id': str(case.id),
            'execution_tx_hash': order_tx_hash,
            'reversibility_ends_at': case.reversibility_ends_at.isoformat(),
        })
        return case

    # REMAND / ESCALATE_COURT — leave the case in AWAITING_OMBUDSMAN
    case.save(update_fields=['ombudsman_order_hash', 'ombudsman_order_tx_hash',
                             'updated_at'])
    return case


# ─────────────────────────────────────────────────────────────────────────────
# OWNERSHIP TRANSFER (legal-person wallets only)
# ─────────────────────────────────────────────────────────────────────────────

class OwnershipTransferError(WalletAccessError):
    code = 'ownership_transfer_error'


def initiate_ownership_transfer(
    *,
    outgoing_user,
    incoming_user_id: Optional[int],
    reason: str,
    grounds: str,
    evidence_bundle_hash: str,
) -> OwnershipTransferCase:
    """
    Filed by the current authorised operator (or by a party with
    documentary authority) to move a legal-person wallet to a new
    operator. Goes through the Ombudsman path because the decision is
    legal in nature.
    """
    wallet = _require_wallet(outgoing_user)
    if wallet.holder_type != 'LEGAL_PERSON':
        raise OwnershipTransferError(
            'Ownership transfer is only applicable to legal-person wallets.'
        )
    if wallet.state in ('RECOVERING', 'OWNERSHIP_TRANSFER', 'RECOVERED', 'SUSPENDED'):
        raise OwnershipTransferError(
            f'Wallet is in state {wallet.state}; transfer cannot be filed now.'
        )

    valid_reasons = {c for c, _ in OwnershipTransferCase.REASON_CHOICES}
    if reason not in valid_reasons:
        raise OwnershipTransferError('Invalid transfer reason.')

    now = timezone.now()
    with db_transaction.atomic():
        case = OwnershipTransferCase.objects.create(
            wallet=wallet,
            status='AWAITING_OMBUDSMAN',
            outgoing_operator=outgoing_user,
            incoming_operator_id=incoming_user_id,
            reason=reason,
            grounds=grounds[:2000],
            evidence_bundle_hash=evidence_bundle_hash[:66],
            public_notice_ends_at=now + OWNERSHIP_TRANSFER_NOTICE,
        )
        wallet.state = 'OWNERSHIP_TRANSFER'
        wallet.save(update_fields=['state', 'last_state_change'])

    # Emit on-chain event (reuses the WalletRecoveryEvents contract with
    # a dedicated case ID namespace)
    try:
        from services.blockchain import BlockchainService
        svc = BlockchainService()
        tx_hash = svc.file_recovery_request(
            case_id=f'ownership:{case.id}',
            original_wallet=wallet.wallet_address,
            claimant_wallet='0x' + '0' * 40,
            path='TRUSTEE',
            evidence_bundle_hash=evidence_bundle_hash,
        )
        case.transfer_requested_tx_hash = tx_hash
        case.save(update_fields=['transfer_requested_tx_hash', 'updated_at'])
    except Exception as exc:  # noqa: BLE001
        logger.warning('file_recovery_request (ownership) emit failed: %s', exc)

    notify(outgoing_user, 'ownership.transfer_filed', {
        'wallet_address': wallet.wallet_address,
        'case_id': str(case.id),
        'reason': reason,
    })
    return case


def cancel_ownership_transfer(user, case_id: int, *, reason: str) -> OwnershipTransferCase:
    wallet = _require_wallet(user)
    case = OwnershipTransferCase.objects.filter(id=case_id, wallet=wallet).first()
    if not case:
        raise OwnershipTransferError('Transfer case not found.')
    if case.status in ('EXECUTED', 'CANCELLED', 'REJECTED', 'EXPIRED'):
        raise OwnershipTransferError(f'Case already {case.status}.')

    case.status = 'CANCELLED'
    case.grounds = (case.grounds + f'\n\nCancelled: {reason[:500]}').strip()
    case.save(update_fields=['status', 'grounds', 'updated_at'])

    wallet.state = 'ACTIVATED' if wallet.password_hash else 'CREATED'
    wallet.save(update_fields=['state', 'last_state_change'])

    notify(user, 'ownership.transfer_cancelled', {
        'wallet_address': wallet.wallet_address,
        'case_id': str(case.id),
    })
    return case


# ─────────────────────────────────────────────────────────────────────────────
# CSV EXPORT — transaction history download
# ─────────────────────────────────────────────────────────────────────────────

def transactions_to_csv(user, *, module: str = '', status_filter: str = '') -> str:
    """
    Export the user's chain_tx_audit_log rows as CSV text.
    Returned as a string; the view wraps it in an HttpResponse.
    """
    import csv
    import io

    from chain.models import TxAuditLog

    qs = TxAuditLog.objects.filter(actor=user).order_by('-created_at')
    if module:
        qs = qs.filter(module=module)
    if status_filter:
        qs = qs.filter(status=status_filter)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        'created_at', 'module', 'action', 'mode', 'chain_id',
        'to_address', 'tx_hash', 'block_number', 'status',
        'client_tx_id', 'confirmed_at',
    ])
    for r in qs[:10000]:    # cap — if users need more, add pagination
        w.writerow([
            r.created_at.isoformat(),
            r.module, r.action, r.mode, r.chain_id,
            r.to_address, r.tx_hash, r.block_number or '', r.status,
            r.client_tx_id,
            r.confirmed_at.isoformat() if r.confirmed_at else '',
        ])
    return buf.getvalue()
