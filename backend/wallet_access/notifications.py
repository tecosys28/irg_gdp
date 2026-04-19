"""
IRG Chain 888101 — Multi-channel notification service.

Every notification the wallet_access system produces is funneled through
`notify(user, event, context)`. The service fans out to the channels
configured for that event.

Channels currently wired:
  * EMAIL   — Django's send_mail, production-ready
  * PUSH    — stub (plug in FCM / APNs / OneSignal as needed)
  * WHATSAPP — stub (plug in MSG91 / Gupshup / Twilio as needed)
  * SMS     — stub (plug in MSG91 / Twilio as needed)

SECURITY RULES:
  * Wallet address, tx hash, status, history — OK to send on any channel.
  * Seed phrase, wallet password, private key — NEVER sent on any channel.
    Any template attempting this will raise ValueError at render time.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# EVENT CATALOG — every event the wallet_access app produces
# ─────────────────────────────────────────────────────────────────────────────

EVENTS = {
    # Triggered after user signup → wallet auto-created on chain.
    'wallet.created': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'Your IRG wallet has been created',
        'urgency': 'normal',
    },

    # Reminder that the user must activate their wallet before they can transact.
    'wallet.activation_required': {
        'channels': ['EMAIL', 'PUSH'],
        'subject': 'Action needed: activate your IRG wallet',
        'urgency': 'normal',
    },

    # Fired once the user has set their wallet password and confirmed the seed.
    'wallet.activated': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'Your IRG wallet is now active',
        'urgency': 'normal',
    },

    # Fired on every successful transaction the user originates.
    'wallet.transaction_executed': {
        'channels': ['EMAIL', 'PUSH'],
        'subject': 'IRG transaction confirmed',
        'urgency': 'normal',
    },

    # Fired when something unusual happens (new device, password change, many
    # failed attempts, etc.). Multi-channel to maximise user awareness.
    'wallet.unusual_activity': {
        'channels': ['EMAIL', 'WHATSAPP', 'SMS', 'PUSH'],
        'subject': 'Security alert on your IRG wallet',
        'urgency': 'high',
    },

    # Inactivity watchdog (activity-based, replaces calendar liveness).
    'wallet.inactivity_prompt': {
        'channels': ['EMAIL', 'WHATSAPP', 'PUSH'],
        'subject': 'IRG: we have not seen you in a year',
        'urgency': 'normal',
    },
    'wallet.inactivity_reminder': {
        'channels': ['EMAIL', 'WHATSAPP', 'SMS', 'PUSH'],
        'subject': 'IRG: please confirm your IRG wallet is still active',
        'urgency': 'high',
    },
    'wallet.inactivity_nominee_alert': {
        'channels': ['EMAIL', 'WHATSAPP', 'SMS'],
        'subject': 'IRG: a wallet you are a nominee on has been silent',
        'urgency': 'high',
    },

    # Ownership transfer (legal-person wallets).
    'ownership.transfer_filed': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'IRG: ownership transfer filed',
        'urgency': 'high',
    },
    'ownership.transfer_cancelled': {
        'channels': ['EMAIL'],
        'subject': 'IRG: ownership transfer cancelled',
        'urgency': 'normal',
    },
    'ownership.transfer_executed': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'IRG: ownership transfer completed',
        'urgency': 'high',
    },

    # Recovery events — urgent because they may signal an attack in progress.
    'recovery.initiated': {
        'channels': ['EMAIL', 'WHATSAPP', 'SMS', 'PUSH'],
        'subject': 'URGENT: Recovery initiated on your IRG wallet',
        'urgency': 'critical',
    },
    'recovery.approved': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'IRG wallet recovery approved',
        'urgency': 'high',
    },
    'recovery.executed': {
        'channels': ['EMAIL', 'WHATSAPP', 'SMS'],
        'subject': 'IRG wallet recovery completed',
        'urgency': 'high',
    },
    'recovery.cancelled': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'IRG wallet recovery cancelled',
        'urgency': 'normal',
    },
    'recovery.rejected': {
        'channels': ['EMAIL'],
        'subject': 'IRG wallet recovery rejected',
        'urgency': 'normal',
    },

    # Nominee-facing.
    'nominee.registered': {
        'channels': ['EMAIL', 'WHATSAPP'],
        'subject': 'You have been registered as a nominee on IRG',
        'urgency': 'normal',
    },
    'nominee.signature_requested': {
        'channels': ['EMAIL', 'WHATSAPP', 'SMS'],
        'subject': 'IRG: Your nominee signature is requested',
        'urgency': 'high',
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SAFETY — forbid secret leakage
# ─────────────────────────────────────────────────────────────────────────────

FORBIDDEN_SUBSTRINGS = (
    'seed_phrase',
    'seed phrase',
    'mnemonic',
    'private_key',
    'private key',
    'wallet_password',
    'wallet password',
    'encrypted_private_key',
)


def _safety_check(context: dict) -> None:
    """
    Raise if any context value contains something that looks like a secret.
    This is a defense-in-depth check — callers should never pass secrets
    into notification context in the first place.
    """
    for key, val in context.items():
        k_lower = str(key).lower()
        if any(f in k_lower for f in FORBIDDEN_SUBSTRINGS):
            raise ValueError(
                f'notification context contains forbidden key: {key}'
            )
        if isinstance(val, str):
            v_lower = val.lower()
            # The value could innocently contain the word "key" — we only
            # flag if it contains the exact forbidden compound tokens.
            for f in FORBIDDEN_SUBSTRINGS:
                if f in v_lower:
                    raise ValueError(
                        f'notification context value for {key} contains forbidden content'
                    )


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE RENDERING
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES: Dict[str, Dict[str, str]] = {
    'wallet.created': {
        'EMAIL': (
            'Hello {name},\n\n'
            'Your IRG wallet has been created successfully.\n\n'
            '  Wallet address: {wallet_address}\n'
            '  IRG Chain: 888101\n'
            '  Created: {created_at}\n\n'
            'IMPORTANT: you cannot yet transact with this wallet. Please open '
            'the app and complete activation by setting your wallet password '
            'and confirming your 15-word seed phrase.\n\n'
            'Keep your seed phrase safe — it is the only way to recover your '
            'wallet if you lose your device. Never share it with anyone, and '
            'never enter it on any website. IRG staff will never ask for it.\n\n'
            '— IRG'
        ),
        'WHATSAPP': (
            'Hello {name}, your IRG wallet has been created.\n'
            'Address: {wallet_address}\n'
            'Please open the app to activate before you can transact.'
        ),
    },

    'wallet.activation_required': {
        'EMAIL': (
            'Hello {name},\n\n'
            'Your IRG wallet ({wallet_address}) is still not activated. '
            'Transactions will remain blocked until you set your wallet '
            'password and confirm your seed phrase in the app.\n\n'
            '— IRG'
        ),
        'PUSH': 'Activate your IRG wallet to start transacting.',
    },

    'wallet.activated': {
        'EMAIL': (
            'Hello {name},\n\n'
            'Your IRG wallet ({wallet_address}) is now active and ready to '
            'use. All your transactions will be recorded on IRG Chain 888101.\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'Your IRG wallet is now active and ready to transact.',
    },

    'wallet.transaction_executed': {
        'EMAIL': (
            'Hello {name},\n\n'
            'A transaction on your IRG wallet has been confirmed on '
            'IRG Chain 888101.\n\n'
            '  Action: {action}\n'
            '  Amount: {amount}\n'
            '  Transaction hash: {tx_hash}\n'
            '  Timestamp: {timestamp}\n\n'
            'If you did not initiate this transaction, please contact IRG '
            'support immediately.\n\n'
            '— IRG'
        ),
        'PUSH': '{action}: {amount} — tx {tx_hash_short}',
    },

    'wallet.unusual_activity': {
        'EMAIL': (
            'SECURITY ALERT\n\n'
            'Hello {name},\n\n'
            'Unusual activity has been detected on your IRG wallet '
            '({wallet_address}):\n\n'
            '  {description}\n\n'
            'If this was you, no action is needed. If not, please contact '
            'IRG support immediately and consider initiating recovery.\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'IRG security alert: {description}. Contact support if this was not you.',
        'SMS': 'IRG alert: {description}. Contact support if not you.',
        'PUSH': 'Security alert: {description}',
    },

    'wallet.inactivity_prompt': {
        'EMAIL': (
            'Hello {name},\n\n'
            'We have not seen any activity on your IRG wallet ({wallet_address}) '
            'for {silent_for_days} days. To keep your nominees from being alerted '
            'unnecessarily, please open the IRG app and tap "Confirm I am active".\n\n'
            'If you no longer use this wallet, no action is needed — but please '
            'be aware that continued silence will, after two further reminders, '
            'result in your registered nominees being informed.\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'IRG: your wallet has been silent for a while. Please open the app and tap "Confirm active".',
        'PUSH': 'We have not seen you in a year — please confirm you are still active.',
    },

    'wallet.inactivity_reminder': {
        'EMAIL': (
            'Reminder — IRG wallet activity check\n\n'
            'Hello {name},\n\n'
            'Two days ago we asked you to confirm activity on your IRG wallet '
            '({wallet_address}). If we do not hear from you within another '
            'two days, your registered nominees will be informed.\n\n'
            'Please open the IRG app and tap "Confirm I am active" if you are '
            'still using this wallet.\n\n— IRG'
        ),
        'WHATSAPP': 'IRG REMINDER: please open the app and confirm your wallet is active. Nominees will be alerted in 2 days if silent.',
        'SMS': 'IRG: please confirm your wallet is active. Nominees alerted in 2 days.',
        'PUSH': 'Second reminder — please confirm wallet activity.',
    },

    'wallet.inactivity_nominee_alert': {
        'EMAIL': (
            'Hello {nominee_name},\n\n'
            'You are a registered nominee on the IRG wallet held by '
            '{nominator_name}. That wallet has been silent for over a year '
            'despite two notifications. You may wish to contact them to check '
            'on their wellbeing, or — if circumstances warrant — consider '
            'initiating a recovery case.\n\n'
            'Wallet address: {wallet_address}\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'IRG: {nominator_name}\'s wallet has been silent for over a year. Please reach out to them.',
        'SMS': 'IRG: wallet you are nominee on has been silent >1 year. Please check on the holder.',
    },

    'ownership.transfer_filed': {
        'EMAIL': (
            'Hello {name},\n\n'
            'An ownership transfer has been filed for your IRG wallet '
            '({wallet_address}).\n\n'
            '  Case ID: {case_id}\n'
            '  Reason: {reason}\n\n'
            'The Ombudsman will review the documents and issue an order. '
            'Transactions on this wallet are paused until resolution.\n\n— IRG'
        ),
        'WHATSAPP': 'IRG: ownership transfer case {case_id} filed. Transactions paused.',
    },

    'ownership.transfer_cancelled': {
        'EMAIL': (
            'The ownership transfer case {case_id} has been cancelled. '
            'No changes were made.\n\n— IRG'
        ),
    },

    'ownership.transfer_executed': {
        'EMAIL': (
            'Ownership transfer {case_id} has been executed. The new authorised '
            'operator has been activated on wallet {wallet_address}. The seed '
            'phrase has been rotated.\n\n— IRG'
        ),
        'WHATSAPP': 'IRG: ownership transfer {case_id} executed.',
    },

    'recovery.initiated': {
        'EMAIL': (
            'URGENT — IRG WALLET RECOVERY INITIATED\n\n'
            'Hello {name},\n\n'
            'A recovery case has been filed against your IRG wallet '
            '({wallet_address}) by:\n\n'
            '  Claimant: {claimant_name}\n'
            '  Path: {path}\n'
            '  Filed: {filed_at}\n'
            '  Case ID: {case_id}\n'
            '  Cooling-off ends: {cooling_off_ends_at}\n\n'
            'IF THIS WAS NOT YOU: Cancel the recovery immediately from the '
            'IRG app. Any cancellation during the cooling-off period stops '
            'the process.\n\n'
            'IF THIS WAS INITIATED BY YOU (e.g. you lost your device): No '
            'action needed unless the case stalls.\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'URGENT: IRG recovery filed on your wallet. Cancel in-app if this was not you.',
        'SMS': 'IRG: recovery case {case_id} filed. Cancel in app if not you.',
        'PUSH': 'URGENT: recovery initiated on your wallet',
    },

    'recovery.approved': {
        'EMAIL': (
            'Hello {name},\n\n'
            'The recovery case on IRG wallet {wallet_address} has been '
            'approved. Execution will proceed shortly. A 90-day '
            'reversibility window applies.\n\n'
            'Case ID: {case_id}\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'IRG recovery case {case_id} approved. Execution will proceed.',
    },

    'recovery.executed': {
        'EMAIL': (
            'Hello {name},\n\n'
            'The recovery on IRG wallet {wallet_address} has been executed. '
            'Assets have been transferred per the approved case details.\n\n'
            '  Case ID: {case_id}\n'
            '  Execution tx: {execution_tx_hash}\n'
            '  Reversibility window ends: {reversibility_ends_at}\n\n'
            '— IRG'
        ),
        'WHATSAPP': 'IRG recovery {case_id} executed. Reversibility window: 90 days.',
        'SMS': 'IRG: recovery {case_id} executed.',
    },

    'recovery.cancelled': {
        'EMAIL': (
            'The recovery case {case_id} on your IRG wallet has been '
            'cancelled. No changes were made to your wallet.\n\n— IRG'
        ),
        'WHATSAPP': 'IRG recovery {case_id} cancelled. No changes made.',
    },

    'recovery.rejected': {
        'EMAIL': (
            'The recovery case {case_id} on IRG wallet {wallet_address} '
            'has been rejected.\n\nReason: {reason}\n\n— IRG'
        ),
    },

    'nominee.registered': {
        'EMAIL': (
            'Hello {nominee_name},\n\n'
            'You have been registered as a nominee on the IRG wallet of '
            '{nominator_name}. In the event of death, incapacity, or loss '
            'of access, you may be called upon to participate in a '
            'recovery process.\n\n'
            'To view or understand your responsibilities, please open the '
            'IRG app.\n\n— IRG'
        ),
        'WHATSAPP': 'You are now a nominee on {nominator_name}\'s IRG wallet.',
    },

    'nominee.signature_requested': {
        'EMAIL': (
            'Hello {nominee_name},\n\n'
            'Your signature is requested on a recovery case for '
            '{nominator_name}\'s IRG wallet. Please open the IRG app to '
            'review and decide.\n\nCase ID: {case_id}\n\n— IRG'
        ),
        'WHATSAPP': 'IRG: signature requested on case {case_id}.',
        'SMS': 'IRG: signature requested on recovery case {case_id}.',
    },
}


def _render(event: str, channel: str, context: dict) -> str:
    tpls = TEMPLATES.get(event, {})
    tpl = tpls.get(channel)
    if not tpl:
        return ''
    # Tolerant formatting — missing context keys become empty strings.
    class _SafeDict(dict):
        def __missing__(self, key):
            return ''
    return tpl.format_map(_SafeDict(context))


# ─────────────────────────────────────────────────────────────────────────────
# CHANNEL ADAPTERS
# ─────────────────────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str) -> bool:
    if not to:
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@irg.example'),
            recipient_list=[to],
            fail_silently=False,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning('Email send failed to=%s: %s', to, exc)
        return False


def _send_whatsapp(to: str, body: str) -> bool:
    """
    WhatsApp stub.

    Plug in your preferred provider (MSG91 / Gupshup / Twilio) by replacing
    the body of this function. Typical implementation:

        import requests
        url = settings.WHATSAPP_PROVIDER['API_URL']
        headers = {'Authorization': f'Bearer {settings.WHATSAPP_PROVIDER["API_KEY"]}'}
        resp = requests.post(url, headers=headers, json={
            'to': to, 'type': 'text', 'text': {'body': body}
        })
        return resp.ok

    Until wired, this logs the intended send so dev/test flows work.
    """
    if not to:
        return False
    logger.info('[WHATSAPP stub] to=%s body=%s', to, body[:200])
    return True


def _send_sms(to: str, body: str) -> bool:
    """SMS stub — plug in MSG91 / Twilio similar to WhatsApp."""
    if not to:
        return False
    logger.info('[SMS stub] to=%s body=%s', to, body[:160])
    return True


def _send_push(to_user, body: str) -> bool:
    """Push stub — plug in FCM / APNs / OneSignal."""
    if not to_user:
        return False
    logger.info('[PUSH stub] user_id=%s body=%s', getattr(to_user, 'id', None), body[:200])
    return True


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NotifyResult:
    sent: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)


def notify(user_or_contact, event: str, context: Optional[dict] = None,
           *, override_channels: Optional[List[str]] = None) -> NotifyResult:
    """
    Send a notification.

    user_or_contact: either a Django User (channels resolved from user's
                     email/mobile) OR a dict like
                     {'email': ..., 'mobile': ..., 'name': ...} for
                     non-user recipients (e.g. a nominee).
    """
    context = dict(context or {})
    _safety_check(context)

    cfg = EVENTS.get(event)
    if not cfg:
        logger.warning('notify: unknown event %s', event)
        return NotifyResult(skipped=['unknown_event'])

    channels = override_channels or list(cfg['channels'])

    # Resolve contact info.
    if isinstance(user_or_contact, dict):
        email = user_or_contact.get('email') or ''
        mobile = user_or_contact.get('mobile') or ''
        context.setdefault('name', user_or_contact.get('name', ''))
        user_obj = None
    else:
        user_obj = user_or_contact
        email = getattr(user_obj, 'email', '') or ''
        mobile = getattr(user_obj, 'mobile', '') or ''
        context.setdefault('name', getattr(user_obj, 'get_full_name', lambda: '')() or email.split('@')[0])

    result = NotifyResult()
    subject = cfg['subject']

    for ch in channels:
        body = _render(event, ch, context)
        if not body:
            result.skipped.append(f'{ch}:no_template')
            continue

        ok = False
        if ch == 'EMAIL':
            ok = _send_email(email, subject, body)
        elif ch == 'WHATSAPP':
            ok = _send_whatsapp(mobile, body)
        elif ch == 'SMS':
            ok = _send_sms(mobile, body)
        elif ch == 'PUSH':
            ok = _send_push(user_obj, body)
        else:
            result.skipped.append(f'{ch}:unknown_channel')
            continue

        (result.sent if ok else result.skipped).append(ch)

    return result
