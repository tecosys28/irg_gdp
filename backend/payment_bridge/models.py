"""
IRG PAA Bridge — Django models

Local mirror of the canonical PAA state. Persists to the GDP backend's
database under db_table prefix `paa_`. Structurally parallels the gov_v3
localStorage layout — fields renamed to snake_case Django conventions.

NB: This is a MIRROR, not a second source of truth. If the bridge is
configured with `transport="http"`, these tables are read-only caches
refreshed from gov_v3. If `transport="django_local"`, these tables are
the authoritative store for GDP's PAA operations.
"""
from django.db import models
import uuid


class PaaCorpusFund(models.Model):
    CF_TYPE_CHOICES = [
        ("IRG_CF", "IRG Super Corpus Fund"),
        ("IRG_Local_CF", "IRG Local Corpus Fund"),
        ("Minter_CF", "Minter Corpus Fund"),
        ("Jeweler_CF", "Jeweler Corpus Fund"),
    ]

    id = models.CharField(max_length=80, primary_key=True)
    cf_type = models.CharField(max_length=20, choices=CF_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=10, default="GLOBAL")
    owner_id = models.CharField(max_length=100, db_index=True)
    primary_currency = models.CharField(max_length=3, default="USD")
    is_multi_currency_account = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    bank_name = models.CharField(max_length=200, blank=True)
    trustee_banker_id = models.CharField(max_length=80, null=True, blank=True)
    trustee_banker_name = models.CharField(max_length=200, blank=True)

    min_required_balance = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    min_required_currency = models.CharField(max_length=3, default="USD")

    # balances stored as [{currency, balance, lastUpdated}]
    balances = models.JSONField(default=list)

    monthly_inflow = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    monthly_outflow = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    ytd_roi = models.DecimalField(max_digits=6, decimal_places=4, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paa_corpus_fund"
        indexes = [models.Index(fields=["cf_type"]), models.Index(fields=["country_code"])]


class PaaTransaction(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("validated", "validated"),
        ("pending_approval", "pending_approval"),
        ("pending_dual", "pending_dual"),
        ("pending_board", "pending_board"),
        ("approved", "approved"),
        ("executed", "executed"),
        ("failed", "failed"),
        ("court_pending", "court_pending"),
        ("cancelled", "cancelled"),
    ]

    id = models.CharField(max_length=80, primary_key=True)
    tx_type = models.CharField(max_length=20)
    category = models.CharField(max_length=40, db_index=True)

    amount = models.DecimalField(max_digits=20, decimal_places=4)
    currency = models.CharField(max_length=3)
    usd_amount = models.DecimalField(max_digits=20, decimal_places=4, null=True)

    from_account = models.CharField(max_length=120)
    to_cf = models.CharField(max_length=20)
    to_account_id = models.CharField(max_length=80, null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending", db_index=True)
    required_approval = models.CharField(max_length=10, null=True, blank=True)
    idempotency_key = models.CharField(max_length=200, db_index=True, unique=True)

    # [{type, confirmed, confirmedAt, confirmedBy, documentHash}]
    oracle_confirmations = models.JSONField(default=list)
    approvals = models.JSONField(default=list)

    budget_hash = models.CharField(max_length=200, null=True, blank=True)
    blockchain_tx_hash = models.CharField(max_length=200, null=True, blank=True)

    source_system = models.CharField(max_length=40, default="gdp")
    source_ref = models.CharField(max_length=200, null=True, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)

    class Meta:
        db_table = "paa_transaction"
        ordering = ["-created_at"]


class PaaBudget(models.Model):
    budget_id = models.CharField(max_length=80, primary_key=True)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    advisory_board_resolution_hash = models.CharField(max_length=200, blank=True)

    # {categoryKey: {maxLimit, currency, periodType, currentUtilization, ...}}
    categories = models.JSONField(default=dict)

    total_corpus_limit = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_corpus_currency = models.CharField(max_length=3, default="USD")
    min_corpus_ratio = models.DecimalField(max_digits=5, decimal_places=4, default=0.6)

    system_support_charge_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0.005)
    roi_share_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0.06)

    is_active = models.BooleanField(default=False, db_index=True)
    updated_by = models.CharField(max_length=100, default="system")
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "paa_budget"


class PaaTrustee(models.Model):
    id = models.CharField(max_length=80, primary_key=True)
    name = models.CharField(max_length=200)
    license_ref = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=10, default="IN")
    status = models.CharField(max_length=20, default="active")

    assigned_cfs = models.JSONField(default=list)
    compliance_factors = models.JSONField(default=dict)
    last_score = models.JSONField(null=True, blank=True)

    last_scored_at = models.DateTimeField(null=True, blank=True)
    last_scored_by = models.CharField(max_length=100, blank=True)

    registered_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paa_trustee"


class PaaCourtApproval(models.Model):
    id = models.CharField(max_length=80, primary_key=True)
    related_rule_change_id = models.CharField(max_length=80, null=True, blank=True)
    related_tx_id = models.CharField(max_length=80, null=True, blank=True)
    document_hash = models.CharField(max_length=200, db_index=True)
    document_url = models.URLField(null=True, blank=True)
    file_name = models.CharField(max_length=200, blank=True)
    uploaded_by = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "paa_court_approval"


class PaaAuditLog(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=40, db_index=True)
    actor = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)

    class Meta:
        db_table = "paa_audit_log"
        ordering = ["-timestamp"]


class PaaRuleChange(models.Model):
    id = models.CharField(max_length=80, primary_key=True)
    proposed_by = models.CharField(max_length=100)
    proposed_at = models.DateTimeField(auto_now_add=True)
    change_type = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict)
    advisory_board_votes = models.JSONField(default=dict)
    required_votes = models.PositiveIntegerField(default=3)
    status = models.CharField(max_length=20, default="voting", db_index=True)
    court_approval_id = models.CharField(max_length=80, null=True, blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    implemented_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "paa_rule_change"
