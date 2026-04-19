"""
IRG Chain 888101 — Wallet access, activation, nominee, device, liveness,
and recovery state.

Key security separations enforced in the schema itself:

  * Django `auth` password    -> login to the backend / app account
  * WalletActivation.password_hash -> unlocks the on-device private key;
                                       the server NEVER sees the plaintext
                                       wallet password. We only store a
                                       PBKDF2 hash of it so we can confirm
                                       that a given password the device
                                       sends during rare recovery flows
                                       (like nominee challenge) matches
                                       what the user set — the actual
                                       private key is decrypted client-side.

  * WalletActivation.seed_phrase_hash -> SHA-256 hash of the 15-word seed
                                         phrase. The plaintext phrase is
                                         shown to the user exactly once,
                                         in-app, during activation.

None of these values ever leave the user's device except as hashes.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# LIFECYCLE
# ─────────────────────────────────────────────────────────────────────────────

class WalletActivation(models.Model):
    """
    One row per user wallet. Tracks the lifecycle, activation timestamp,
    and the bare-minimum cryptographic commitments needed to support
    device re-binding and recovery WITHOUT ever holding the plaintext
    wallet password, private key, or seed phrase on the server.
    """

    STATE_CHOICES = [
        ('CREATED', 'Created — awaiting activation'),
        ('ACTIVATED', 'Activated — ready for transactions'),
        ('LOCKED', 'Locked — too many failed attempts'),
        ('RECOVERING', 'Recovery in progress'),
        ('OWNERSHIP_TRANSFER', 'Ownership transfer in progress (legal-person wallets)'),
        ('SUSPENDED', 'Suspended'),
        ('RECOVERED', 'Recovered — superseded'),
    ]

    HOLDER_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Natural person'),
        ('LEGAL_PERSON', 'Company, LLP, trust, firm, HUF, cooperative, etc.'),
    ]

    ENTITY_TYPE_CHOICES = [
        ('', '—'),
        ('PRIVATE_LTD', 'Private limited company'),
        ('PUBLIC_LTD_LISTED', 'Public limited — listed'),
        ('PUBLIC_LTD_UNLISTED', 'Public limited — unlisted'),
        ('LLP', 'Limited liability partnership'),
        ('PARTNERSHIP', 'Partnership firm'),
        ('PROPRIETORSHIP', 'Proprietorship'),
        ('PUBLIC_TRUST', 'Public trust'),
        ('PRIVATE_TRUST', 'Private trust'),
        ('COOPERATIVE', 'Cooperative society'),
        ('HUF', 'Hindu Undivided Family'),
        ('OTHER', 'Other legal entity'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet_activation',
    )
    wallet_address = models.CharField(max_length=66, unique=True, db_index=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='CREATED', db_index=True)

    # Who owns this wallet — natural person or legal entity.
    holder_type = models.CharField(
        max_length=14, choices=HOLDER_TYPE_CHOICES, default='INDIVIDUAL',
    )
    # Only populated when holder_type == LEGAL_PERSON. Fuller KYC lives on
    # the existing CorporateProfile / AuthorizedSignatory models; these two
    # fields exist so the wallet screen can show "IRG Ltd — Private Limited
    # Company" without joining to other tables.
    legal_entity_name = models.CharField(max_length=200, blank=True)
    entity_type = models.CharField(max_length=24, choices=ENTITY_TYPE_CHOICES, blank=True, default='')

    # PBKDF2-SHA256 hash of the wallet encryption password, created on-device
    # during activation and sent to the server ONCE for verification during
    # recovery challenges. Empty until activation.
    password_hash = models.CharField(max_length=256, blank=True)
    password_algo = models.CharField(max_length=32, blank=True, default='pbkdf2_sha256')
    password_iterations = models.PositiveIntegerField(default=600000)
    password_salt = models.CharField(max_length=64, blank=True)

    # SHA-256 hash of the 15-word BIP-39 seed phrase. The plaintext is
    # shown to the user exactly once during activation.
    seed_phrase_hash = models.CharField(max_length=66, blank=True)
    seed_phrase_confirmed = models.BooleanField(default=False)
    seed_phrase_confirmed_at = models.DateTimeField(null=True, blank=True)

    # Failed-attempt counter, cleared on successful recovery / reset.
    failed_password_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    # Activity tracking — used by the inactivity watchdog.
    # Touched on login, transaction, and explicit liveness confirmation.
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)
    inactivity_prompt_sent_at = models.DateTimeField(null=True, blank=True)
    inactivity_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    nominees_alerted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    last_state_change = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_activation'

    def __str__(self) -> str:
        return f'{self.wallet_address} [{self.state}]'

    # ── lifecycle helpers ──
    @property
    def is_transactable(self) -> bool:
        """Can this wallet currently be used to originate a transaction?"""
        if self.state != 'ACTIVATED':
            return False
        if self.locked_until and self.locked_until > timezone.now():
            return False
        return True

    @property
    def blocking_reason(self) -> str:
        """Human-readable reason the wallet cannot transact — shown in UI."""
        if self.state == 'CREATED':
            return 'Wallet not activated. Please set your wallet password.'
        if self.state == 'LOCKED':
            return 'Wallet locked due to repeated failed password attempts.'
        if self.state == 'RECOVERING':
            return 'A recovery is in progress. Transactions paused until resolved.'
        if self.state == 'OWNERSHIP_TRANSFER':
            return 'An ownership transfer is in progress. Transactions paused until resolved.'
        if self.state == 'SUSPENDED':
            return 'Wallet suspended. Please contact support or the Ombudsman.'
        if self.state == 'RECOVERED':
            return 'This wallet has been recovered to another address. It can no longer transact.'
        return ''

    def touch_activity(self):
        """Record activity so the inactivity watchdog resets its clock."""
        self.last_activity_at = timezone.now()
        # Clear any in-flight inactivity prompts since the user is clearly active.
        self.inactivity_prompt_sent_at = None
        self.inactivity_reminder_sent_at = None
        self.nominees_alerted_at = None
        self.save(update_fields=[
            'last_activity_at', 'inactivity_prompt_sent_at',
            'inactivity_reminder_sent_at', 'nominees_alerted_at',
            'last_state_change',
        ])


# ─────────────────────────────────────────────────────────────────────────────
# NOMINEES
# ─────────────────────────────────────────────────────────────────────────────

class NomineeRegistration(models.Model):
    """
    Nominee designation for social recovery and succession. At least two
    nominees are required before the wallet can receive or originate any
    asset-bearing transaction; this is enforced in TransactionGuard.
    """

    wallet = models.ForeignKey(
        WalletActivation,
        on_delete=models.CASCADE,
        related_name='nominees',
    )
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=60)   # spouse, child, sibling, friend, etc.

    # Contact — used for recovery notifications. We deliberately do NOT store
    # the nominee's own wallet address here — that's resolved at recovery
    # time so lost/updated nominee wallets don't orphan this record.
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)

    # For binding proof-of-relationship in a legal succession matter.
    # IPFS hash of supporting document (PAN, ID, relationship proof).
    id_document_hash = models.CharField(max_length=66, blank=True)

    # Share of the wallet's assets allocated to this nominee on succession.
    # Sum across all nominees must equal 100 before the wallet can transact.
    share_percent = models.DecimalField(max_digits=6, decimal_places=3, default=0)

    # Threshold for social recovery: how many of the wallet's nominees must
    # co-sign to recover. Stored per-nominee but typically same value across
    # all rows — kept per-row so the schema gracefully handles per-nominee
    # weightings in future.
    social_recovery_threshold = models.PositiveSmallIntegerField(default=2)

    # When this nominee was notified of their designation (they should know).
    notified_at = models.DateTimeField(null=True, blank=True)

    # For revocation history — soft-delete so audit trail is preserved.
    active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_nominee'
        indexes = [
            models.Index(fields=['wallet', 'active']),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# DEVICES
# ─────────────────────────────────────────────────────────────────────────────

class WalletDevice(models.Model):
    """
    A device that holds the encrypted private key for the wallet. Only one
    device may be ACTIVE at a time; rebinding a new device triggers a
    cooling-off period before the new device can transact (defends against
    "thief steals phone, immediately rebinds" attacks).
    """

    STATE_CHOICES = [
        ('PENDING', 'Pending cooling-off period'),
        ('ACTIVE', 'Active — can sign transactions'),
        ('RETIRED', 'Retired — superseded by rebind'),
        ('REVOKED', 'Revoked by user or system'),
    ]

    wallet = models.ForeignKey(
        WalletActivation,
        on_delete=models.CASCADE,
        related_name='devices',
    )
    # Hash of the device's hardware fingerprint + user salt. Never the raw ID.
    device_id_hash = models.CharField(max_length=66, db_index=True)
    device_label = models.CharField(max_length=100, blank=True)  # "iPhone 14 Pro", user-provided
    platform = models.CharField(max_length=20, blank=True)        # ios / android / web

    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='PENDING')

    # Cooling-off period for new device bindings. Configurable but typically
    # 24–72 hours depending on the user's risk profile.
    cooling_off_until = models.DateTimeField(null=True, blank=True)

    # On-chain registration of this device via DeviceP2PRegistry.
    bind_tx_hash = models.CharField(max_length=66, blank=True)
    revoke_tx_hash = models.CharField(max_length=66, blank=True)

    bound_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'wallet_device'
        indexes = [
            models.Index(fields=['wallet', 'state']),
        ]

    def __str__(self) -> str:
        return f'{self.device_label or self.device_id_hash[:10]} ({self.state})'


# ─────────────────────────────────────────────────────────────────────────────
# INACTIVITY EVENTS
# ─────────────────────────────────────────────────────────────────────────────

class InactivityEvent(models.Model):
    """
    Audit trail for the inactivity watchdog. One row per prompt, reminder,
    nominee alert, or confirmation. Supersedes the calendar-based liveness
    check — the watchdog now fires only when a wallet has seen no login,
    transaction, or confirmation in 1 year.
    """

    KIND_CHOICES = [
        ('PROMPT_SENT', 'First prompt — "we have not seen you in a year"'),
        ('REMINDER_SENT', 'Reminder sent 2 days after prompt with no response'),
        ('NOMINEES_ALERTED', 'Nominees informed due to continued silence'),
        ('CONFIRMED', 'User confirmed they are still active'),
    ]

    wallet = models.ForeignKey(
        'WalletActivation',
        on_delete=models.CASCADE,
        related_name='inactivity_events',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True)
    detail = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'wallet_inactivity_event'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['wallet', 'occurred_at']),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# RECOVERY CASES
# ─────────────────────────────────────────────────────────────────────────────

class RecoveryCase(models.Model):
    """
    A wallet recovery case. Three paths exist:

      SELF:       user restores via seed phrase on a new device. No human
                  review. Fast path. Blocks old device, starts new device's
                  cooling-off, no on-chain recovery event emitted beyond
                  the device rebind.

      SOCIAL:     nominees co-sign a recovery to a claimant-controlled
                  wallet. Cooling-off period and public notice apply.
                  Capped at low-value thresholds; above the cap this path
                  auto-escalates to TRUSTEE.

      TRUSTEE:    high-value, death / incapacity / dispute cases. We emit
                  a WalletRecoveryRequested event; the existing IRG
                  Ombudsman system handles preliminary review, hearing,
                  and Ombudsman Order. We listen for OmbudsmanOrderIssued
                  and execute the Order mechanically.

    Only TRUSTEE cases interact with the Ombudsman office. This app holds
    no Ombudsman logic of its own.
    """

    PATH_CHOICES = [
        ('SELF', 'Self-recovery via seed phrase'),
        ('SOCIAL', 'Social recovery via nominees'),
        ('TRUSTEE', 'Trustee-assisted, Ombudsman-ordered recovery'),
    ]

    STATUS_CHOICES = [
        ('FILED', 'Filed — initial submission'),
        ('NOTIFIED', 'Original owner notified, cooling-off running'),
        ('AWAITING_SIGNATURES', 'Awaiting nominee co-signatures (SOCIAL only)'),
        ('AWAITING_OMBUDSMAN', 'Awaiting Ombudsman review (TRUSTEE only)'),
        ('APPROVED', 'Approved — ready for execution'),
        ('EXECUTED', 'Executed — assets moved to claimant wallet'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled by original owner during cooling-off'),
        ('EXPIRED', 'Expired without completion'),
    ]

    # Subject of the recovery.
    original_wallet = models.ForeignKey(
        WalletActivation,
        on_delete=models.PROTECT,
        related_name='recovery_cases',
    )

    path = models.CharField(max_length=10, choices=PATH_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='FILED', db_index=True)

    # Claimant — the person asking to recover. May be the original owner
    # (self / social), a nominee (social), or a legal heir (trustee).
    claimant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='filed_recovery_cases',
    )
    claimant_wallet_address = models.CharField(max_length=66, blank=True)

    # Free-text grounds. For TRUSTEE cases, evidence is hashed below.
    grounds = models.TextField(blank=True)

    # IPFS hash of the evidence bundle (death certificate, succession
    # certificate, court order, affidavits, etc.). Plaintext documents
    # live off-chain per DPDP Act; only the hash is stored here and on-chain.
    evidence_bundle_hash = models.CharField(max_length=66, blank=True)

    # Cooling-off and notice timings.
    cooling_off_ends_at = models.DateTimeField(null=True, blank=True)
    public_notice_ends_at = models.DateTimeField(null=True, blank=True)

    # Link into your existing Ombudsman system (on-chain handoff).
    # When status transitions to AWAITING_OMBUDSMAN we emit a
    # WalletRecoveryRequested event and store the resulting tx hash here.
    recovery_requested_tx_hash = models.CharField(max_length=66, blank=True)

    # When your Ombudsman system issues the Order, this is populated.
    ombudsman_order_hash = models.CharField(max_length=66, blank=True)  # IPFS hash of the Order document
    ombudsman_order_tx_hash = models.CharField(max_length=66, blank=True)  # On-chain OmbudsmanOrderIssued event

    # Execution — the transaction that actually moved the assets.
    execution_tx_hash = models.CharField(max_length=66, blank=True)

    # Reversibility window — after execution, a court order can undo within
    # this period.
    reversibility_ends_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_recovery_case'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['path', 'status']),
            models.Index(fields=['original_wallet', 'status']),
        ]


class NomineeSignature(models.Model):
    """Nominee co-signature for a SOCIAL recovery case."""

    case = models.ForeignKey(RecoveryCase, on_delete=models.CASCADE, related_name='nominee_signatures')
    nominee = models.ForeignKey(NomineeRegistration, on_delete=models.PROTECT)
    signature = models.CharField(max_length=200)           # ECDSA signature over the case payload
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wallet_nominee_signature'
        unique_together = [('case', 'nominee')]


# ─────────────────────────────────────────────────────────────────────────────
# OWNERSHIP TRANSFER (legal-person wallets only)
# ─────────────────────────────────────────────────────────────────────────────

class OwnershipTransferCase(models.Model):
    """
    Records a change in who legally owns a legal-person wallet (acquisition,
    partnership restructuring, trustee succession, sale as going concern, etc.).
    The wallet address does NOT change; the seed phrase is rotated and the
    human operator link moves to the new authorised person.

    This is distinct from RecoveryCase. Recovery is "something is broken";
    ownership transfer is "the corporate paperwork moved underneath a
    healthy wallet". The machinery overlaps — both require Ombudsman
    review, both emit on-chain events, both pause transactions during the
    notice period — so both models look similar, but semantically they are
    different cases and should not be conflated in reports.
    """

    STATUS_CHOICES = [
        ('FILED', 'Filed'),
        ('AWAITING_OMBUDSMAN', 'Awaiting Ombudsman review'),
        ('APPROVED', 'Approved — seed rotation pending new operator'),
        ('EXECUTED', 'Executed — new operator activated'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled by current operator or entity'),
        ('EXPIRED', 'Expired without completion'),
    ]

    wallet = models.ForeignKey(
        WalletActivation,
        on_delete=models.PROTECT,
        related_name='ownership_transfers',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='FILED', db_index=True)

    # Existing operator (who files the transfer — may be empty if they
    # are no longer available).
    outgoing_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='outgoing_wallet_transfers',
    )
    # Incoming operator — who the wallet should be transferred to. Their
    # KYC must already be complete.
    incoming_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incoming_wallet_transfers',
    )

    # Reason for the transfer — short code for reports, free-text grounds.
    REASON_CHOICES = [
        ('ACQUISITION', 'Company acquired / shareholding changed'),
        ('PARTNERSHIP_CHANGE', 'Partnership reconstituted'),
        ('TRUSTEE_SUCCESSION', 'Trustee succession'),
        ('PROP_SALE', 'Proprietorship sold as going concern'),
        ('OPERATOR_DEPARTED', 'Authorised operator left the entity'),
        ('OTHER', 'Other — see grounds'),
    ]
    reason = models.CharField(max_length=24, choices=REASON_CHOICES, default='OTHER')
    grounds = models.TextField(blank=True)

    # IPFS hash of the evidence bundle (board resolution, sale deed,
    # partnership amendment, trustee nomination, etc.).
    evidence_bundle_hash = models.CharField(max_length=66, blank=True)

    # Notice period (same as trustee recovery).
    public_notice_ends_at = models.DateTimeField(null=True, blank=True)

    # On-chain integration.
    transfer_requested_tx_hash = models.CharField(max_length=66, blank=True)
    ombudsman_order_hash = models.CharField(max_length=66, blank=True)
    ombudsman_order_tx_hash = models.CharField(max_length=66, blank=True)
    execution_tx_hash = models.CharField(max_length=66, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_ownership_transfer_case'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
