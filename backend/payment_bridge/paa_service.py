"""
IRG PAA Bridge — Django-local paa_service
==========================================
Python twin of `irg_gov/src/modules/payments/paaService.js`. Method names,
signatures, return shapes, and validation rules are identical. The only
difference is the storage substrate: gov_v3 writes to localStorage via
datastore.js, this writes to the Django ORM via payment_bridge.models.

This is the authoritative implementation when the bridge is configured
with transport="django_local". In production, set transport="http" and
this module becomes a fallback / local mirror.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction as _db_tx
from django.utils import timezone

from . import paa_schema
from .models import (
    PaaCorpusFund, PaaTransaction, PaaBudget, PaaTrustee,
    PaaCourtApproval, PaaAuditLog, PaaRuleChange,
)


# ─────────────────────────────────────────────────────────────────────────────
# utilities
# ─────────────────────────────────────────────────────────────────────────────
def _uid(prefix: str = "p") -> str:
    return f"{prefix}_{int(time.time()*1000):x}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return timezone.now().isoformat()


def _to_decimal(v) -> Decimal:
    return Decimal(str(v))


def _anchor_hash(payload: Dict[str, Any]) -> str:
    # Lightweight deterministic hash — the Python stand-in for the gov_v3
    # in-memory blockchain's SHA-256 proof-of-work anchor. Real deployments
    # swap this for an on-chain call.
    return "0x" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _cf_to_dict(cf: PaaCorpusFund) -> Dict[str, Any]:
    return {
        "id": cf.id, "cfType": cf.cf_type, "name": cf.name,
        "countryCode": cf.country_code, "ownerId": cf.owner_id,
        "primaryCurrency": cf.primary_currency,
        "isMultiCurrencyAccount": cf.is_multi_currency_account,
        "isActive": cf.is_active, "bankName": cf.bank_name,
        "trusteeBankerId": cf.trustee_banker_id,
        "trusteeBankerName": cf.trustee_banker_name,
        "minRequiredBalance": float(cf.min_required_balance or 0),
        "minRequiredCurrency": cf.min_required_currency,
        "balances": cf.balances,
        "monthlyInflow": float(cf.monthly_inflow or 0),
        "monthlyOutflow": float(cf.monthly_outflow or 0),
        "ytdROI": float(cf.ytd_roi or 0),
        "lastUpdated": cf.last_updated.isoformat() if cf.last_updated else None,
    }


def _tx_to_dict(tx: PaaTransaction) -> Dict[str, Any]:
    return {
        "id": tx.id, "txType": tx.tx_type, "category": tx.category,
        "amount": float(tx.amount), "currency": tx.currency,
        "usdAmount": float(tx.usd_amount) if tx.usd_amount is not None else None,
        "fromAccount": tx.from_account, "toCF": tx.to_cf,
        "toAccountId": tx.to_account_id, "status": tx.status,
        "requiredApproval": tx.required_approval,
        "idempotencyKey": tx.idempotency_key,
        "oracleConfirmations": tx.oracle_confirmations,
        "approvals": tx.approvals,
        "budgetHash": tx.budget_hash,
        "blockchainTxHash": tx.blockchain_tx_hash,
        "sourceSystem": tx.source_system,
        "sourceRef": tx.source_ref,
        "notes": tx.notes,
        "createdBy": tx.created_by,
        "createdAt": tx.created_at.isoformat() if tx.created_at else None,
        "executedAt": tx.executed_at.isoformat() if tx.executed_at else None,
        "cancelledAt": tx.cancelled_at.isoformat() if tx.cancelled_at else None,
        "cancelReason": tx.cancel_reason,
    }


def _audit(action: str, payload: Dict[str, Any], actor: str = "SYSTEM") -> None:
    if action not in paa_schema.AUDIT_ACTIONS:
        # Still persist but this flags a schema drift
        payload = {**payload, "_unknown_action": True}
    PaaAuditLog.objects.create(action=action, actor=actor, payload=payload)


# ─────────────────────────────────────────────────────────────────────────────
# Rules engine (pure)
# ─────────────────────────────────────────────────────────────────────────────
def _validate_transaction(candidate: Dict[str, Any],
                          active_budget: Optional[PaaBudget],
                          cfs: List[PaaCorpusFund]) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # Schema sanity
    if candidate["category"] not in paa_schema.TRANSACTION_CATEGORIES:
        errors.append({"code": "UNKNOWN_CATEGORY", "message": f"Unknown category {candidate['category']}"})
    if candidate["currency"] not in paa_schema.SUPPORTED_CURRENCIES:
        errors.append({"code": "UNSUPPORTED_CURRENCY", "message": f"Currency {candidate['currency']} not supported"})
    if not isinstance(candidate["amount"], (int, float, Decimal)) or float(candidate["amount"]) <= 0:
        errors.append({"code": "INVALID_AMOUNT", "message": "amount must be positive"})
    if not candidate.get("idempotencyKey"):
        warnings.append({"code": "MISSING_IDEMPOTENCY_KEY", "message": "no idempotency key supplied"})

    if errors:
        return {"isValid": False, "errors": errors, "warnings": warnings}

    # Idempotency
    idem = candidate.get("idempotencyKey")
    if idem:
        existing = PaaTransaction.objects.filter(idempotency_key=idem).first()
        if existing:
            errors.append({
                "code": "DUPLICATE_TRANSACTION",
                "message": f"idempotency key {idem} already exists (id={existing.id})",
            })
            return {"isValid": False, "errors": errors, "warnings": warnings,
                    "duplicateOf": existing.id}

    # Budget compliance
    budget_utilisation = None
    if active_budget is None:
        warnings.append({"code": "NO_ACTIVE_BUDGET",
                         "message": "no active budget — category limits not enforced"})
    else:
        cats = active_budget.categories or {}
        cat = cats.get(candidate["category"])
        if cat is None:
            errors.append({"code": "CATEGORY_NOT_BUDGETED",
                           "message": f"category {candidate['category']} not in budget"})
        else:
            cur = float(cat.get("currentUtilization", 0) or 0)
            amt = float(candidate["amount"])
            after = cur + amt
            limit = float(cat.get("maxLimit", 0) or 0)
            pct = (after / limit * 100) if limit else 0
            budget_utilisation = {
                "categoryLimit": limit, "currentUtilization": cur,
                "afterTransaction": after, "utilizationPercent": pct,
                "isNearLimit": 85 <= pct < 100, "isOverLimit": pct > 100,
            }
            if budget_utilisation["isOverLimit"]:
                errors.append({"code": "BUDGET_LIMIT_EXCEEDED",
                               "message": f"exceeds budget {limit}; after {after}"})
            elif budget_utilisation["isNearLimit"]:
                warnings.append({"code": "BUDGET_NEAR_LIMIT",
                                 "message": f"budget will be {pct:.1f}% utilised"})

    # Corpus ratio (payment only)
    if candidate["txType"] == "payment":
        min_ratio = float(active_budget.min_corpus_ratio) if active_budget else paa_schema.DEFAULT_CHARGE_RATES["MIN_CORPUS_RATIO"]
        total_usd = 0.0
        for cf in cfs:
            for b in (cf.balances or []):
                total_usd += paa_schema.to_usd(float(b.get("balance", 0)), b.get("currency", "USD"))
        tx_usd = paa_schema.to_usd(float(candidate["amount"]), candidate["currency"])
        remaining = total_usd - tx_usd
        ratio = (remaining / total_usd) if total_usd > 0 else 1.0
        if total_usd > 0 and ratio < min_ratio:
            errors.append({
                "code": "CORPUS_RATIO_VIOLATION",
                "message": f"breaches min corpus ratio {min_ratio:.0%} (after {ratio:.1%})",
            })

    # Oracle warnings
    for oracle in paa_schema.get_oracle_requirements_for(candidate["category"]):
        given = candidate.get("oracleConfirmations") or []
        have = any(c.get("type") == oracle and c.get("confirmed") for c in given)
        if not have:
            warnings.append({"code": "PENDING_ORACLE",
                             "message": f"awaiting {oracle} confirmation"})

    # Routing + approval level
    usd_amount = paa_schema.to_usd(float(candidate["amount"]), candidate["currency"])
    required_approval = paa_schema.get_approval_level_for(usd_amount)
    routing = {
        "destinationCF": paa_schema.get_routing_for(candidate["category"]),
        "requiredOracles": list(paa_schema.get_oracle_requirements_for(candidate["category"])),
        "priority": "urgent" if candidate["category"] in ("recall_compensation", "recall_insurance_claim")
                    else "high" if candidate["category"] in ("advisory_board_expense", "taxes")
                    else "normal",
    }

    return {
        "isValid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "routing": routing,
        "budgetUtilisation": budget_utilisation,
        "requiredApproval": required_approval,
        "usdAmount": usd_amount,
    }


def _initial_status_for(level: str) -> str:
    return {
        "court":  "court_pending",
        "board":  "pending_board",
        "dual":   "pending_dual",
        "single": "pending_approval",
    }.get(level, "pending_approval")


def _compute_trustee_score(factors: Dict[str, float]) -> Dict[str, Any]:
    total = 0.0
    total_weight = 0.0
    breakdown = {}
    for key, defn in paa_schema.COMPLIANCE_FACTORS.items():
        score = float(factors.get(key, 0) or 0)
        w = defn["weight"]
        breakdown[key] = {**defn, "score": score, "contribution": score * w}
        total += score * w
        total_weight += w
    return {"overall": total / total_weight if total_weight else 0, "breakdown": breakdown}


# ─────────────────────────────────────────────────────────────────────────────
# SDK method implementations — names match sdk.js SDK_METHODS
# ─────────────────────────────────────────────────────────────────────────────
def listCorpusFunds(filter_: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    qs = PaaCorpusFund.objects.all()
    if filter_:
        if filter_.get("cfType"): qs = qs.filter(cf_type=filter_["cfType"])
        if filter_.get("ownerId"): qs = qs.filter(owner_id=filter_["ownerId"])
        if filter_.get("countryCode"): qs = qs.filter(country_code=filter_["countryCode"])
    return [_cf_to_dict(cf) for cf in qs]


def getCorpusFund(cf_id: str) -> Optional[Dict[str, Any]]:
    cf = PaaCorpusFund.objects.filter(id=cf_id).first()
    return _cf_to_dict(cf) if cf else None


def getSuperCorpus() -> Optional[Dict[str, Any]]:
    cf = PaaCorpusFund.objects.filter(cf_type="IRG_CF").first()
    return _cf_to_dict(cf) if cf else None


def totalCorpusValueUSD() -> float:
    total = 0.0
    for cf in PaaCorpusFund.objects.all():
        for b in (cf.balances or []):
            total += paa_schema.to_usd(float(b.get("balance", 0)), b.get("currency", "USD"))
    return total


def listTransactions(filter_: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    qs = PaaTransaction.objects.all()
    if filter_:
        if filter_.get("status"): qs = qs.filter(status=filter_["status"])
        if filter_.get("cfType"): qs = qs.filter(to_cf=filter_["cfType"])
        if filter_.get("category"): qs = qs.filter(category=filter_["category"])
        if filter_.get("createdBy"): qs = qs.filter(created_by=filter_["createdBy"])
        if filter_.get("sourceSystem"): qs = qs.filter(source_system=filter_["sourceSystem"])
    return [_tx_to_dict(tx) for tx in qs]


def getTransaction(tx_id: str) -> Optional[Dict[str, Any]]:
    tx = PaaTransaction.objects.filter(id=tx_id).first()
    return _tx_to_dict(tx) if tx else None


@_db_tx.atomic
def createTransaction(payload: Dict[str, Any], actor: str = "system") -> Dict[str, Any]:
    candidate = {
        "txType":   payload.get("txType"),
        "category": payload.get("category"),
        "amount":   float(payload.get("amount", 0) or 0),
        "currency": payload.get("currency"),
        "fromAccount": payload.get("fromAccount", ""),
        "idempotencyKey": payload.get("idempotencyKey") or _uid("idem"),
        "oracleConfirmations": payload.get("oracleConfirmations") or [],
    }
    active_budget = PaaBudget.objects.filter(is_active=True).first()
    cfs = list(PaaCorpusFund.objects.all())
    validation = _validate_transaction(candidate, active_budget, cfs)
    if not validation["isValid"]:
        _audit("TRANSACTION_FAILED", {"input": payload, "validation": validation}, actor)
        return {"ok": False, "validation": validation}

    dest_cf = validation["routing"]["destinationCF"]
    to_account_id = payload.get("toAccountId") or (
        (PaaCorpusFund.objects.filter(cf_type=dest_cf).first() or type("x", (), {"id": None})).id
    )

    tx_id = _uid("tx")
    tx = PaaTransaction.objects.create(
        id=tx_id,
        tx_type=candidate["txType"], category=candidate["category"],
        amount=_to_decimal(candidate["amount"]), currency=candidate["currency"],
        usd_amount=_to_decimal(validation["usdAmount"]),
        from_account=candidate["fromAccount"],
        to_cf=dest_cf, to_account_id=to_account_id,
        status=_initial_status_for(validation["requiredApproval"]),
        required_approval=validation["requiredApproval"],
        idempotency_key=candidate["idempotencyKey"],
        oracle_confirmations=candidate["oracleConfirmations"],
        approvals=[],
        budget_hash=(active_budget.advisory_board_resolution_hash if active_budget else None),
        blockchain_tx_hash=None,
        source_system=payload.get("sourceSystem", "gdp"),
        source_ref=payload.get("sourceRef"),
        notes=payload.get("notes", ""),
        created_by=actor,
    )
    anchored = _anchor_hash({"entity": "transaction", "txId": tx.id, "type": "TRANSACTION_CREATED"})
    tx.blockchain_tx_hash = anchored
    tx.save(update_fields=["blockchain_tx_hash"])
    _audit("TRANSACTION_CREATED", {"txId": tx.id, "summary": _tx_to_dict(tx)}, actor)
    return {"ok": True, "transaction": _tx_to_dict(tx), "validation": validation}


@_db_tx.atomic
def approveTransaction(tx_id: str, actor: str,
                       role: str = "AdvisoryBoardMember") -> Dict[str, Any]:
    tx = PaaTransaction.objects.select_for_update().filter(id=tx_id).first()
    if not tx:
        return {"ok": False, "error": "Transaction not found"}

    approvals = list(tx.approvals or [])
    if any(a.get("actor") == actor for a in approvals):
        return {"ok": False, "error": "already approved by this actor"}
    approvals.append({"actor": actor, "role": role, "approvedAt": _now_iso()})

    needed = {"single": 1, "dual": 2, "board": 3, "court": 3}.get(tx.required_approval or "single", 1)
    new_status = "approved" if len(approvals) >= needed else tx.status
    tx.approvals = approvals
    tx.status = new_status
    tx.save()
    _audit("TRANSACTION_APPROVED", {"txId": tx.id, "by": actor, "status": new_status}, actor)
    return {"ok": True, "transaction": _tx_to_dict(tx)}


@_db_tx.atomic
def executeTransaction(tx_id: str, actor: str = "system") -> Dict[str, Any]:
    tx = PaaTransaction.objects.select_for_update().filter(id=tx_id).first()
    if not tx:
        return {"ok": False, "error": "Transaction not found"}
    if tx.status != "approved":
        return {"ok": False, "error": f"cannot execute from status {tx.status}"}

    required = paa_schema.get_oracle_requirements_for(tx.category)
    confirmed_types = {c.get("type") for c in (tx.oracle_confirmations or []) if c.get("confirmed")}
    missing = [r for r in required if r not in confirmed_types]
    if missing:
        return {"ok": False, "error": f"missing oracle confirmations: {', '.join(missing)}"}

    # Apply balance delta to the target CF (if known)
    if tx.to_account_id:
        cf = PaaCorpusFund.objects.select_for_update().filter(id=tx.to_account_id).first()
        if cf:
            sign = -1 if tx.tx_type in ("payment", "system_charge") else 1
            bals = list(cf.balances or [])
            idx = next((i for i, b in enumerate(bals) if b.get("currency") == tx.currency), None)
            delta = sign * float(tx.amount)
            if idx is None:
                bals.append({"currency": tx.currency, "balance": delta, "lastUpdated": _now_iso()})
            else:
                bals[idx]["balance"] = float(bals[idx].get("balance", 0)) + delta
                bals[idx]["lastUpdated"] = _now_iso()
            cf.balances = bals
            cf.save(update_fields=["balances", "last_updated"])

    # Bump budget utilisation
    budget = PaaBudget.objects.select_for_update().filter(is_active=True).first()
    if budget and tx.category in (budget.categories or {}):
        cats = dict(budget.categories)
        cat = dict(cats[tx.category])
        cat["currentUtilization"] = float(cat.get("currentUtilization", 0) or 0) + float(tx.amount)
        cats[tx.category] = cat
        budget.categories = cats
        budget.save(update_fields=["categories", "updated_at"])

    tx.status = "executed"
    tx.executed_at = timezone.now()
    tx.save(update_fields=["status", "executed_at"])
    _audit("TRANSACTION_EXECUTED", {"txId": tx.id}, actor)
    return {"ok": True, "transaction": _tx_to_dict(tx)}


@_db_tx.atomic
def cancelTransaction(tx_id: str, actor: str, reason: str = "") -> Dict[str, Any]:
    tx = PaaTransaction.objects.select_for_update().filter(id=tx_id).first()
    if not tx:
        return {"ok": False, "error": "Transaction not found"}
    if tx.status in ("executed", "cancelled"):
        return {"ok": False, "error": f"cannot cancel from status {tx.status}"}
    tx.status = "cancelled"
    tx.cancelled_at = timezone.now()
    tx.cancel_reason = reason
    tx.save(update_fields=["status", "cancelled_at", "cancel_reason"])
    _audit("TRANSACTION_CANCELLED", {"txId": tx.id, "reason": reason}, actor)
    return {"ok": True, "transaction": _tx_to_dict(tx)}


@_db_tx.atomic
def recordOracleConfirmation(tx_id: str, oracle_type: str, actor: str,
                              document_hash: Optional[str] = None) -> Dict[str, Any]:
    tx = PaaTransaction.objects.select_for_update().filter(id=tx_id).first()
    if not tx:
        return {"ok": False, "error": "Transaction not found"}
    confirmations = list(tx.oracle_confirmations or [])
    idx = next((i for i, c in enumerate(confirmations) if c.get("type") == oracle_type), None)
    entry = {
        "type": oracle_type, "confirmed": True,
        "confirmedAt": _now_iso(), "confirmedBy": actor,
        "documentHash": document_hash,
    }
    if idx is None:
        confirmations.append(entry)
    else:
        confirmations[idx] = {**confirmations[idx], **entry}
    tx.oracle_confirmations = confirmations
    tx.save(update_fields=["oracle_confirmations"])
    _audit("ORACLE_CONFIRMED", {"txId": tx.id, "oracleType": oracle_type}, actor)
    return {"ok": True, "transaction": _tx_to_dict(tx)}


# ─────────────────────────────────────────────────────────────────────────────
# Corpus fund create
# ─────────────────────────────────────────────────────────────────────────────
def createCorpusFund(payload: Dict[str, Any], actor: str = "system") -> Dict[str, Any]:
    cf_id = payload.get("id") or _uid("cf")
    cf = PaaCorpusFund.objects.create(
        id=cf_id,
        cf_type=payload["cfType"],
        name=payload["name"],
        country_code=payload.get("countryCode", "GLOBAL"),
        owner_id=payload.get("ownerId", ""),
        primary_currency=payload.get("primaryCurrency", "USD"),
        is_multi_currency_account=bool(payload.get("isMultiCurrencyAccount", False)),
        bank_name=payload.get("bankName", ""),
        trustee_banker_id=payload.get("trusteeBankerId"),
        trustee_banker_name=payload.get("trusteeBankerName", ""),
        min_required_balance=_to_decimal(payload.get("minRequiredBalance", 0)),
        min_required_currency=payload.get("minRequiredCurrency",
                                          payload.get("primaryCurrency", "USD")),
        balances=payload.get("balances", []),
    )
    _audit("CF_CREATED", {"cfId": cf.id, "cfType": cf.cf_type}, actor)
    return _cf_to_dict(cf)


# ─────────────────────────────────────────────────────────────────────────────
# Budget / Rule change
# ─────────────────────────────────────────────────────────────────────────────
def getActiveBudget() -> Optional[Dict[str, Any]]:
    b = PaaBudget.objects.filter(is_active=True).first()
    if not b:
        return None
    return {
        "budgetId": b.budget_id, "version": b.version,
        "effectiveFrom": b.effective_from.isoformat() if b.effective_from else None,
        "effectiveTo": b.effective_to.isoformat() if b.effective_to else None,
        "advisoryBoardResolutionHash": b.advisory_board_resolution_hash,
        "categories": b.categories, "totalCorpusLimit": float(b.total_corpus_limit or 0),
        "totalCorpusCurrency": b.total_corpus_currency,
        "minCorpusRatio": float(b.min_corpus_ratio or 0),
        "systemSupportChargeRate": float(b.system_support_charge_rate or 0),
        "roiShareRate": float(b.roi_share_rate or 0),
        "updatedBy": b.updated_by, "updatedAt": b.updated_at.isoformat() if b.updated_at else None,
        "notes": b.notes,
    }


def proposeBudget(proposal: Dict[str, Any], actor: str) -> Dict[str, Any]:
    rc = PaaRuleChange.objects.create(
        id=_uid("rc"),
        proposed_by=actor,
        change_type=proposal.get("changeType", "budget_revision"),
        title=proposal.get("title", "Budget revision"),
        description=proposal.get("description", ""),
        changes=proposal.get("changes", {}),
        required_votes=proposal.get("requiredVotes", 3),
    )
    _audit("BUDGET_PROPOSED", {"id": rc.id, "title": rc.title}, actor)
    return {"id": rc.id, "proposedBy": rc.proposed_by, "title": rc.title, "status": rc.status}


def voteOnRuleChange(rc_id: str, actor: str, vote: str = "approve",
                     comments: str = "") -> Dict[str, Any]:
    rc = PaaRuleChange.objects.filter(id=rc_id).first()
    if not rc:
        return {"ok": False, "error": "rule change not found"}
    votes = dict(rc.advisory_board_votes or {})
    votes[actor] = {"vote": vote, "votedAt": _now_iso(), "comments": comments}
    approves = sum(1 for v in votes.values() if v["vote"] == "approve")
    if approves >= rc.required_votes:
        rc.status = "approved"
    rc.advisory_board_votes = votes
    rc.save()
    _audit("BUDGET_VOTED", {"id": rc.id, "by": actor, "vote": vote, "status": rc.status}, actor)
    return {"ok": True, "ruleChange": {"id": rc.id, "status": rc.status, "votes": votes}}


def applyApprovedRuleChange(rc_id: str, actor: str) -> Dict[str, Any]:
    rc = PaaRuleChange.objects.filter(id=rc_id).first()
    if not rc:
        return {"ok": False, "error": "rule change not found"}
    if rc.status not in ("approved", "court_approved"):
        return {"ok": False, "error": "not in approved state"}
    new_budget = (rc.changes or {}).get("newBudget")
    if new_budget and new_budget.get("budgetId"):
        # Flip active flags
        PaaBudget.objects.filter(is_active=True).update(is_active=False)
        PaaBudget.objects.update_or_create(
            budget_id=new_budget["budgetId"],
            defaults={
                "version": new_budget.get("version", 1),
                "effective_from": new_budget.get("effectiveFrom") or timezone.now(),
                "categories": new_budget.get("categories", {}),
                "total_corpus_limit": _to_decimal(new_budget.get("totalCorpusLimit", 0)),
                "total_corpus_currency": new_budget.get("totalCorpusCurrency", "USD"),
                "min_corpus_ratio": _to_decimal(new_budget.get("minCorpusRatio", 0.6)),
                "system_support_charge_rate": _to_decimal(new_budget.get("systemSupportChargeRate", 0.005)),
                "roi_share_rate": _to_decimal(new_budget.get("roiShareRate", 0.06)),
                "is_active": True,
                "updated_by": actor,
                "notes": new_budget.get("notes", ""),
            },
        )
    rc.status = "implemented"
    rc.implemented_at = timezone.now()
    rc.implemented_by = actor
    rc.save()
    _audit("BUDGET_REVISED", {"id": rc.id, "by": actor}, actor)
    return {"ok": True, "ruleChange": {"id": rc.id, "status": rc.status}}


# ─────────────────────────────────────────────────────────────────────────────
# Court approval
# ─────────────────────────────────────────────────────────────────────────────
def uploadCourtApproval(payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    c = PaaCourtApproval.objects.create(
        id=_uid("court"),
        related_rule_change_id=payload.get("relatedRuleChangeId"),
        related_tx_id=payload.get("relatedTxId"),
        document_hash=payload["documentHash"],
        document_url=payload.get("documentUrl"),
        file_name=payload.get("fileName", "court_approval.pdf"),
        uploaded_by=actor,
        notes=payload.get("notes", ""),
    )
    if c.related_rule_change_id:
        rc = PaaRuleChange.objects.filter(id=c.related_rule_change_id).first()
        if rc:
            rc.status = "court_approved"
            rc.court_approval_id = c.id
            rc.save(update_fields=["status", "court_approval_id"])
    _audit("COURT_APPROVAL_UPLOADED", {"id": c.id, "hash": c.document_hash}, actor)
    return {"id": c.id, "documentHash": c.document_hash, "fileName": c.file_name}


# ─────────────────────────────────────────────────────────────────────────────
# Trustees
# ─────────────────────────────────────────────────────────────────────────────
def listTrustees() -> List[Dict[str, Any]]:
    return [
        {
            "id": t.id, "name": t.name, "licenseRef": t.license_ref,
            "country": t.country, "status": t.status,
            "assignedCFs": t.assigned_cfs, "complianceFactors": t.compliance_factors,
            "lastScore": t.last_score,
            "lastScoredAt": t.last_scored_at.isoformat() if t.last_scored_at else None,
            "lastScoredBy": t.last_scored_by,
            "registeredAt": t.registered_at.isoformat() if t.registered_at else None,
        }
        for t in PaaTrustee.objects.all()
    ]


def getTrustee(trustee_id: str) -> Optional[Dict[str, Any]]:
    lst = listTrustees()
    return next((t for t in lst if t["id"] == trustee_id), None)


def registerTrustee(payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    t = PaaTrustee.objects.create(
        id=payload.get("id") or _uid("tb"),
        name=payload["name"],
        license_ref=payload.get("licenseRef", ""),
        country=payload.get("country", "IN"),
        assigned_cfs=payload.get("assignedCFs", []),
    )
    _audit("TRUSTEE_REGISTERED", {"id": t.id, "name": t.name}, actor)
    return {"id": t.id, "name": t.name, "status": t.status}


def scoreTrustee(trustee_id: str, factors: Dict[str, float], actor: str) -> Dict[str, Any]:
    t = PaaTrustee.objects.filter(id=trustee_id).first()
    if not t:
        return {"ok": False, "error": "trustee not found"}
    merged = {**(t.compliance_factors or {}), **factors}
    score = _compute_trustee_score(merged)
    t.compliance_factors = merged
    t.last_score = score
    t.last_scored_at = timezone.now()
    t.last_scored_by = actor
    t.save()
    _audit("TRUSTEE_SCORE_UPDATED", {"id": t.id, "overall": score["overall"]}, actor)
    return {"ok": True, "trustee": {"id": t.id, "lastScore": score}}


# ─────────────────────────────────────────────────────────────────────────────
# Audit / dashboard
# ─────────────────────────────────────────────────────────────────────────────
def getAuditLog(filter_: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    qs = PaaAuditLog.objects.all()
    if filter_:
        if filter_.get("action"): qs = qs.filter(action=filter_["action"])
        if filter_.get("actor"):  qs = qs.filter(actor=filter_["actor"])
    return [
        {
            "id": str(e.id), "timestamp": e.timestamp.isoformat(),
            "action": e.action, "actor": e.actor, "payload": e.payload,
        }
        for e in qs[:1000]
    ]


def getDashboardMetrics() -> Dict[str, Any]:
    txs = PaaTransaction.objects.all()
    inflow_usd = outflow_usd = 0.0
    executed = 0
    pending = 0
    for tx in txs:
        if tx.status == "executed":
            executed += 1
            usd = paa_schema.to_usd(float(tx.amount), tx.currency)
            if tx.tx_type == "collection":
                inflow_usd += usd
            elif tx.tx_type in ("payment", "system_charge"):
                outflow_usd += usd
        elif tx.status.startswith("pending") or tx.status == "court_pending":
            pending += 1
    return {
        "totalCorpusValueUSD": totalCorpusValueUSD(),
        "corpusFundCount": PaaCorpusFund.objects.count(),
        "transactionsTotal": txs.count(),
        "transactionsExecuted": executed,
        "transactionsPending": pending,
        "inflowYTD": inflow_usd,
        "outflowYTD": outflow_usd,
        "activeBudgetVersion": (PaaBudget.objects.filter(is_active=True).first().version
                                if PaaBudget.objects.filter(is_active=True).exists() else None),
        "chainHeight": PaaAuditLog.objects.count(),
    }


def snapshotState() -> Dict[str, Any]:
    return {
        "corpusFunds": listCorpusFunds(),
        "transactions": listTransactions(),
        "activeBudget": getActiveBudget(),
        "trustees": listTrustees(),
        "chainStats": {"height": PaaAuditLog.objects.count()},
        "timestamp": _now_iso(),
    }


__all__ = [
    "listCorpusFunds", "getCorpusFund", "getSuperCorpus", "totalCorpusValueUSD",
    "listTransactions", "getTransaction",
    "createTransaction", "approveTransaction", "executeTransaction",
    "cancelTransaction", "recordOracleConfirmation",
    "createCorpusFund",
    "getActiveBudget", "proposeBudget", "voteOnRuleChange", "applyApprovedRuleChange",
    "uploadCourtApproval",
    "listTrustees", "getTrustee", "registerTrustee", "scoreTrustee",
    "getAuditLog", "getDashboardMetrics", "snapshotState",
]
