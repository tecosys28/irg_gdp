"""
Core Signals - Model event handlers
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import hashlib
import logging

from django.db import transaction as db_transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import User, UserRole, KYCDocument

logger = logging.getLogger(__name__)


def _kyc_tier_to_int(tier_str: str) -> int:
    """Map core.User.kyc_tier enum to the integer IdentityRegistry expects."""
    return {
        'NONE': 0,
        'BASIC': 1,
        'ENHANCED': 2,
        'FULL': 3,
    }.get((tier_str or '').upper(), 0)


@receiver(post_save, sender=User)
def create_user_blockchain_address(sender, instance, created, **kwargs):
    """
    When a new user is registered:
      1. Derive a deterministic blockchain address and save it.
      2. After the DB transaction commits, push an identity-registration
         transaction to IRG Chain 888101 via the middleware. This is the
         v2.7 "auto-create wallet for every registered user" flow — note
         that the actual private key is generated on the user's device
         (mobile / browser); Django only records the public address.
    """
    if not created:
        return

    # 1. Deterministic placeholder address if the device hasn't sent one yet.
    if not instance.blockchain_address:
        addr = '0x' + hashlib.sha256(f"{instance.email}{instance.id}".encode()).hexdigest()[:40]
        User.objects.filter(id=instance.id).update(blockchain_address=addr)
        instance.blockchain_address = addr

    # 2. On-chain registration — deferred until the DB transaction commits so
    #    retries don't race against the User row that triggered them.
    def _register_on_chain():
        try:
            from services.blockchain import BlockchainService
            svc = BlockchainService()
            svc.register_user(
                wallet_address=instance.blockchain_address,
                kyc_tier=_kyc_tier_to_int(getattr(instance, 'kyc_tier', 'NONE')),
                jurisdiction=getattr(instance, 'country', 'IN') or 'IN',
                meta={
                    'user_id': instance.id,
                    'email_hash': hashlib.sha256((instance.email or '').encode()).hexdigest(),
                },
            )
        except Exception as exc:  # noqa: BLE001 — never block user creation on chain issues
            logger.warning('register_user failed for user=%s: %s', instance.id, exc)

    # 3. Create the WalletActivation row (state = CREATED) and notify the user.
    def _create_wallet_row_and_notify():
        try:
            from wallet_access.models import WalletActivation
            from wallet_access.notifications import notify
            WalletActivation.objects.get_or_create(
                user=instance,
                defaults={
                    'wallet_address': instance.blockchain_address,
                    'state': 'CREATED',
                },
            )
            notify(instance, 'wallet.created', {
                'wallet_address': instance.blockchain_address,
                'created_at': instance.created_at.isoformat() if getattr(instance, 'created_at', None) else '',
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning('wallet row/notify failed for user=%s: %s', instance.id, exc)

    db_transaction.on_commit(_register_on_chain)
    db_transaction.on_commit(_create_wallet_row_and_notify)


@receiver(post_save, sender=UserRole)
def update_user_kyc_tier(sender, instance, **kwargs):
    """Update user KYC tier when roles change"""
    if instance.status == 'ACTIVE':
        user = instance.user
        active_roles = user.roles.filter(status='ACTIVE').count()

        if active_roles >= 3:
            user.kyc_tier = 'FULL'
        elif active_roles >= 2:
            user.kyc_tier = 'ENHANCED'
        elif active_roles >= 1:
            user.kyc_tier = 'BASIC'

        user.save()


@receiver(post_save, sender=KYCDocument)
def update_user_verification_status(sender, instance, **kwargs):
    """Update user verification flags when KYC docs are verified"""
    if instance.status == 'VERIFIED':
        user = instance.user

        if instance.document_type == 'AADHAAR':
            user.aadhaar_verified = True
        elif instance.document_type == 'PAN':
            user.pan_verified = True
        elif instance.document_type == 'BANK_STATEMENT':
            user.bank_verified = True

        # Update KYC tier
        verified_count = sum([user.aadhaar_verified, user.pan_verified, user.bank_verified])
        if verified_count >= 3:
            user.kyc_tier = 'FULL'
        elif verified_count >= 2:
            user.kyc_tier = 'ENHANCED'
        elif verified_count >= 1:
            user.kyc_tier = 'BASIC'

        user.save()
