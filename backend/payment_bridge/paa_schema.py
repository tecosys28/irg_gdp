"""
IRG PAA Bridge — Canonical Schema (Python port)
================================================

Port of `irg_gov/src/modules/payments/schema.js`. Must stay in LOCKSTEP
with the JS source — both are versioned by PAYMENTS_SCHEMA_VERSION and
the bridge refuses to talk to a peer on a different version.

If you change this file, change schema.js too and bump the version.

IPR Owner: Mr. Rohit Tidke
© 2026 Intech Research Group
"""
from __future__ import annotations
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA VERSION
# ─────────────────────────────────────────────────────────────────────────────
PAYMENTS_SCHEMA_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# USER ROLES
# ─────────────────────────────────────────────────────────────────────────────
USER_ROLES = (
    "SuperAdmin",
    "AdvisoryBoardMember",
    "TrusteeBanker",
    "Minter",
    "Jeweler",
    "Licensee",
    "Auditor",
    "System",
)

# ─────────────────────────────────────────────────────────────────────────────
# CORPUS FUND TYPES
# ─────────────────────────────────────────────────────────────────────────────
CORPUS_FUND_TYPES = ("IRG_CF", "IRG_Local_CF", "Minter_CF", "Jeweler_CF")
SUPER_CORPUS_FUND_TYPE = "IRG_CF"

# ─────────────────────────────────────────────────────────────────────────────
# TRANSACTION TYPES
# ─────────────────────────────────────────────────────────────────────────────
TRANSACTION_TYPES = (
    "collection", "payment", "investment", "roi_credit",
    "recall", "refund", "system_charge", "exchange",
)

# ─────────────────────────────────────────────────────────────────────────────
# TRANSACTION CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
TRANSACTION_CATEGORIES = (
    # Collections (inflows)
    "trot_book_sale", "license_fee", "irg_gdp_sale", "irg_ftr_sale",
    "default_compensation", "recall_compensation", "recall_insurance_claim",
    "dac_charges", "advertisement_charges", "referral_commission_ftr",
    "ftr_minting_cost", "gdp_minting_cost", "ftr_recall_costs",
    "gdp_shortfall", "gdp_recovery",
    "roi_investment_proceeds", "trade_profit",
    "tgdp_ftr_gic_jr_sale", "jewelry_designer_charges",
    "cross_currency_gain", "system_support_charges", "other_collection",
    # Payments (outflows)
    "advisory_board_expense", "taxes", "investments",
    "trust_beneficiary_income", "cross_currency_loss",
    "operational_expense", "other_payment",
)

# ─────────────────────────────────────────────────────────────────────────────
# TRANSACTION STATUSES
# ─────────────────────────────────────────────────────────────────────────────
TRANSACTION_STATUSES = (
    "pending", "validated", "pending_approval",
    "pending_dual", "pending_board", "approved",
    "executed", "failed", "court_pending", "cancelled",
)

# ─────────────────────────────────────────────────────────────────────────────
# CURRENCIES
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_CURRENCIES = (
    "USD", "EUR", "GBP", "INR", "AED", "SGD", "JPY", "AUD", "CAD", "CHF",
)

CURRENCY_DECIMALS = {
    "USD": 2, "EUR": 2, "GBP": 2, "INR": 2, "AED": 2, "SGD": 2,
    "JPY": 0, "AUD": 2, "CAD": 2, "CHF": 2,
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY → CF ROUTING
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_ROUTING = {
    # IRG_CF (super corpus)
    "trot_book_sale":           "IRG_CF",
    "license_fee":              "IRG_CF",
    "ftr_minting_cost":         "IRG_CF",
    "gdp_minting_cost":         "IRG_CF",
    "trust_beneficiary_income": "IRG_CF",
    "advisory_board_expense":   "IRG_CF",
    "taxes":                    "IRG_CF",
    "investments":              "IRG_CF",
    "roi_investment_proceeds":  "IRG_CF",
    "trade_profit":             "IRG_CF",
    # IRG_Local_CF
    "default_compensation":     "IRG_Local_CF",
    "recall_compensation":      "IRG_Local_CF",
    "recall_insurance_claim":   "IRG_Local_CF",
    "dac_charges":              "IRG_Local_CF",
    "advertisement_charges":    "IRG_Local_CF",
    "referral_commission_ftr":  "IRG_Local_CF",
    "ftr_recall_costs":         "IRG_Local_CF",
    "gdp_shortfall":            "IRG_Local_CF",
    "gdp_recovery":             "IRG_Local_CF",
    "tgdp_ftr_gic_jr_sale":     "IRG_Local_CF",
    "jewelry_designer_charges": "IRG_Local_CF",
    "system_support_charges":   "IRG_Local_CF",
    "operational_expense":      "IRG_Local_CF",
    "other_collection":         "IRG_Local_CF",
    "other_payment":            "IRG_Local_CF",
    # Minter_CF
    "irg_ftr_sale":             "Minter_CF",
    "cross_currency_gain":      "Minter_CF",
    "cross_currency_loss":      "Minter_CF",
    # Jeweler_CF
    "irg_gdp_sale":             "Jeweler_CF",
}

# ─────────────────────────────────────────────────────────────────────────────
# ORACLE REQUIREMENTS
# ─────────────────────────────────────────────────────────────────────────────
ORACLE_REQUIREMENTS = {
    "recall_insurance_claim":   ("law_firm", "bank"),
    "investments":              ("trustee",),
    "roi_investment_proceeds":  ("trustee", "bank"),
    "trust_beneficiary_income": ("trustee",),
    "taxes":                    ("bank",),
    "advisory_board_expense":   ("bank",),
    "tgdp_ftr_gic_jr_sale":     ("bank",),
}

ORACLE_TYPES = ("bank", "law_firm", "blockchain", "trustee", "system")

# ─────────────────────────────────────────────────────────────────────────────
# APPROVAL THRESHOLDS (USD-equivalent)
# ─────────────────────────────────────────────────────────────────────────────
APPROVAL_THRESHOLDS_USD = {
    "SINGLE_APPROVAL": 0,
    "DUAL_APPROVAL":   1_000,
    "BOARD_APPROVAL":  10_000,
    "COURT_APPROVAL":  1_000_000,
}

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM CHARGES
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_CHARGE_RATES = {
    "SYSTEM_SUPPORT_CHARGE_RATE": 0.0050,
    "ROI_SHARE_RATE":             0.0600,
    "MIN_CORPUS_RATIO":           0.6000,
}

# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE FACTORS
# ─────────────────────────────────────────────────────────────────────────────
COMPLIANCE_FACTORS = {
    "ROI_PERFORMANCE":      {"weight": 0.25, "label": "ROI performance"},
    "GUIDELINE_ADHERENCE":  {"weight": 0.25, "label": "Guideline adherence"},
    "REPORTING_TIMELINESS": {"weight": 0.15, "label": "Reporting timeliness"},
    "TRANSACTION_ACCURACY": {"weight": 0.15, "label": "Transaction accuracy"},
    "RISK_MANAGEMENT":      {"weight": 0.10, "label": "Risk management"},
    "RESPONSE_TIME":        {"weight": 0.10, "label": "Response time"},
}

# ─────────────────────────────────────────────────────────────────────────────
# AUDIT ACTIONS
# ─────────────────────────────────────────────────────────────────────────────
AUDIT_ACTIONS = (
    "TRANSACTION_CREATED", "TRANSACTION_VALIDATED", "TRANSACTION_APPROVED",
    "TRANSACTION_EXECUTED", "TRANSACTION_FAILED", "TRANSACTION_CANCELLED",
    "BUDGET_PROPOSED", "BUDGET_VOTED", "BUDGET_APPROVED", "BUDGET_REVISED",
    "COURT_APPROVAL_UPLOADED", "CF_CREATED", "CF_DEPOSIT", "CF_WITHDRAWAL",
    "CF_RECONCILED", "TRUSTEE_REGISTERED", "TRUSTEE_REVOKED",
    "TRUSTEE_SCORE_UPDATED", "EXCHANGE_RATE_RECORDED", "ORACLE_CONFIRMED",
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_PAYMENT_CATS = frozenset({
    "advisory_board_expense", "taxes", "investments",
    "trust_beneficiary_income", "cross_currency_loss",
    "operational_expense", "other_payment",
    "recall_compensation", "recall_insurance_claim",
    "ftr_recall_costs", "gdp_shortfall",
})

def is_collection_category(category: str) -> bool:
    return category not in _PAYMENT_CATS

def get_routing_for(category: str) -> str:
    return CATEGORY_ROUTING.get(category, "IRG_Local_CF")

def get_oracle_requirements_for(category: str) -> tuple:
    return ORACLE_REQUIREMENTS.get(category, ())

def get_approval_level_for(usd_amount: float) -> str:
    if usd_amount >= APPROVAL_THRESHOLDS_USD["COURT_APPROVAL"]:
        return "court"
    if usd_amount >= APPROVAL_THRESHOLDS_USD["BOARD_APPROVAL"]:
        return "board"
    if usd_amount >= APPROVAL_THRESHOLDS_USD["DUAL_APPROVAL"]:
        return "dual"
    return "single"


# ─────────────────────────────────────────────────────────────────────────────
# FX rates (static fallback — override via set_rates())
# ─────────────────────────────────────────────────────────────────────────────
_STATIC_USD_RATES = {
    "USD": 1.0000, "EUR": 1.0850, "GBP": 1.2680, "INR": 0.0120,
    "AED": 0.2723, "SGD": 0.7430, "JPY": 0.0066, "AUD": 0.6580,
    "CAD": 0.7345, "CHF": 1.1200,
}
_overrides: dict = {}

def set_rate(currency: str, usd_value: float) -> None:
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"unsupported currency: {currency}")
    if not isinstance(usd_value, (int, float)) or usd_value <= 0:
        raise ValueError(f"invalid usd_value: {usd_value}")
    _overrides[currency] = float(usd_value)

def set_rates(rate_map: dict) -> None:
    for c, v in rate_map.items():
        set_rate(c, v)

def get_usd_rate(currency: str) -> float:
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"unsupported currency: {currency}")
    return _overrides.get(currency, _STATIC_USD_RATES[currency])

def to_usd(amount: float, currency: str) -> float:
    return float(amount) * get_usd_rate(currency)

def convert(amount: float, frm: str, to: str) -> float:
    if frm == to:
        return float(amount)
    return float(amount) * get_usd_rate(frm) / get_usd_rate(to)


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency key — same shape as the JS SDK
# ─────────────────────────────────────────────────────────────────────────────
def make_idempotency_key(source_system: str, source_ref, category: str,
                         amount, currency: str) -> str:
    import time as _time
    ref = source_ref or f"nullref_{int(_time.time() * 1000)}"
    return f"{source_system}|{category}|{currency}|{amount}|{ref}"
