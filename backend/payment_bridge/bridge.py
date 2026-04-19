"""
IRG PAA Bridge — Python SDK
============================

Peer of `irg_gov/src/modules/payments/sdk.js`. Lets any Python service
(Django, FastAPI, Celery worker, plain script) post inflows / payments /
corpus operations through the canonical IRG Payment Autonomy module that
lives in gov_v3.

Supported transports:

  * "http"             — POST to a gov_v3-hosted proxy endpoint
                        (production path; gov_v3 ships buildHTTPHandler
                         from sdk.js to mount it).
  * "callback"         — call a user-supplied dispatcher function
                        (for in-process testing or alternate backends).
  * "django_local"     — call the in-repo Django paa_service module
                        directly (demo / dev loop; GDP's default).

Every call is { method, args, request_id, schema_version } and every
response is { ok, data } or { ok: False, error }.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from . import paa_schema

# ─────────────────────────────────────────────────────────────────────────────
# Method allow-list — must match sdk.js exactly.
# ─────────────────────────────────────────────────────────────────────────────
SDK_METHODS = (
    # Reads
    "listCorpusFunds", "getCorpusFund", "getSuperCorpus", "totalCorpusValueUSD",
    "listTransactions", "getTransaction",
    "getActiveBudget", "listTrustees", "getTrustee",
    "getAuditLog", "getDashboardMetrics", "snapshotState",
    # Writes
    "createTransaction", "approveTransaction", "executeTransaction",
    "cancelTransaction", "recordOracleConfirmation",
    "createCorpusFund", "proposeBudget", "voteOnRuleChange",
    "applyApprovedRuleChange", "uploadCourtApproval",
    "registerTrustee", "scoreTrustee",
)


class PAABridgeError(Exception):
    """Raised when the bridge cannot complete a call and no {ok,error}
    envelope is available (e.g. network failure, mis-configured transport)."""


class PAABridge:
    """Thin, stateless client. Create one per process; safe to share."""

    def __init__(
        self,
        *,
        transport: str = "django_local",
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        send: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        actor: str = "system",
        source_system: str = "unknown",
        expect_schema_version: Optional[str] = None,
        request_timeout_sec: float = 15.0,
    ):
        self.transport = transport
        self.endpoint = endpoint
        self.api_key = api_key
        self.send = send
        self.actor = actor
        self.source_system = source_system
        self.request_timeout_sec = request_timeout_sec

        if expect_schema_version and expect_schema_version != paa_schema.PAYMENTS_SCHEMA_VERSION:
            raise PAABridgeError(
                f"schema version mismatch: SDK is {paa_schema.PAYMENTS_SCHEMA_VERSION}, "
                f"consumer pinned {expect_schema_version}"
            )
        if transport == "http" and not endpoint:
            raise PAABridgeError("http transport requires endpoint=")
        if transport == "callback" and send is None:
            raise PAABridgeError("callback transport requires send=")

    # ── Public API (1:1 with sdk.js SDK_METHODS) ────────────────────────────
    def list_corpus_funds(self, filter_: Optional[Dict[str, Any]] = None):
        return self._call("listCorpusFunds", [filter_ or {}])

    def get_corpus_fund(self, cf_id: str):
        return self._call("getCorpusFund", [cf_id])

    def get_super_corpus(self):
        return self._call("getSuperCorpus", [])

    def total_corpus_value_usd(self):
        return self._call("totalCorpusValueUSD", [])

    def list_transactions(self, filter_: Optional[Dict[str, Any]] = None):
        return self._call("listTransactions", [filter_ or {}])

    def get_transaction(self, tx_id: str):
        return self._call("getTransaction", [tx_id])

    def get_active_budget(self):
        return self._call("getActiveBudget", [])

    def list_trustees(self):
        return self._call("listTrustees", [])

    def get_trustee(self, trustee_id: str):
        return self._call("getTrustee", [trustee_id])

    def get_audit_log(self, filter_: Optional[Dict[str, Any]] = None):
        return self._call("getAuditLog", [filter_ or {}])

    def get_dashboard_metrics(self):
        return self._call("getDashboardMetrics", [])

    def snapshot_state(self):
        return self._call("snapshotState", [])

    def create_transaction(self, payload: Dict[str, Any], actor: Optional[str] = None):
        return self._call("createTransaction", [payload, actor or self.actor])

    def approve_transaction(self, tx_id: str, actor: Optional[str] = None,
                            role: str = "AdvisoryBoardMember"):
        return self._call("approveTransaction", [tx_id, actor or self.actor, role])

    def execute_transaction(self, tx_id: str, actor: Optional[str] = None):
        return self._call("executeTransaction", [tx_id, actor or self.actor])

    def cancel_transaction(self, tx_id: str, actor: Optional[str] = None, reason: str = ""):
        return self._call("cancelTransaction", [tx_id, actor or self.actor, reason])

    def record_oracle_confirmation(self, tx_id: str, oracle_type: str,
                                   actor: Optional[str] = None, document_hash: Optional[str] = None):
        return self._call(
            "recordOracleConfirmation",
            [tx_id, oracle_type, actor or self.actor, document_hash],
        )

    def create_corpus_fund(self, payload: Dict[str, Any], actor: Optional[str] = None):
        return self._call("createCorpusFund", [payload, actor or self.actor])

    def propose_budget(self, proposal: Dict[str, Any], actor: Optional[str] = None):
        return self._call("proposeBudget", [proposal, actor or self.actor])

    def vote_on_rule_change(self, rc_id: str, actor: Optional[str] = None,
                            vote: str = "approve", comments: str = ""):
        return self._call("voteOnRuleChange", [rc_id, actor or self.actor, vote, comments])

    def apply_approved_rule_change(self, rc_id: str, actor: Optional[str] = None):
        return self._call("applyApprovedRuleChange", [rc_id, actor or self.actor])

    def upload_court_approval(self, payload: Dict[str, Any], actor: Optional[str] = None):
        return self._call("uploadCourtApproval", [payload, actor or self.actor])

    def register_trustee(self, payload: Dict[str, Any], actor: Optional[str] = None):
        return self._call("registerTrustee", [payload, actor or self.actor])

    def score_trustee(self, trustee_id: str, factors: Dict[str, float],
                      actor: Optional[str] = None):
        return self._call("scoreTrustee", [trustee_id, factors, actor or self.actor])

    # ── Convenience helpers (match sdk.js wrappers) ─────────────────────────
    def post_collection(self, *, category: str, amount: float, currency: str,
                        from_account: str, source_ref: Optional[str] = None,
                        oracle_confirmations: Optional[List[Dict[str, Any]]] = None,
                        notes: str = ""):
        return self.create_transaction({
            "txType": "collection",
            "category": category,
            "amount": amount,
            "currency": currency,
            "fromAccount": from_account,
            "sourceSystem": self.source_system,
            "sourceRef": source_ref,
            "notes": notes,
            "oracleConfirmations": oracle_confirmations or [],
            "idempotencyKey": paa_schema.make_idempotency_key(
                self.source_system, source_ref, category, amount, currency
            ),
        })

    def request_payment(self, *, category: str, amount: float, currency: str,
                        from_account: str, source_ref: Optional[str] = None,
                        oracle_confirmations: Optional[List[Dict[str, Any]]] = None,
                        notes: str = ""):
        return self.create_transaction({
            "txType": "payment",
            "category": category,
            "amount": amount,
            "currency": currency,
            "fromAccount": from_account,
            "sourceSystem": self.source_system,
            "sourceRef": source_ref,
            "notes": notes,
            "oracleConfirmations": oracle_confirmations or [],
            "idempotencyKey": paa_schema.make_idempotency_key(
                self.source_system, source_ref, category, amount, currency
            ),
        })

    def credit_roi(self, *, cf_id: str, amount: float, currency: str,
                   source_ref: str, period: str, notes: str = ""):
        return self.create_transaction({
            "txType": "roi_credit",
            "category": "roi_investment_proceeds",
            "amount": amount,
            "currency": currency,
            "fromAccount": "investment_pool",
            "toAccountId": cf_id,
            "sourceSystem": self.source_system,
            "sourceRef": source_ref,
            "notes": notes or f"ROI for {period}",
            "oracleConfirmations": [{"type": "trustee", "confirmed": True}],
            "idempotencyKey": paa_schema.make_idempotency_key(
                self.source_system, source_ref, "roi_investment_proceeds", amount, currency
            ),
        })

    def meta(self) -> Dict[str, Any]:
        return {
            "schemaVersion": paa_schema.PAYMENTS_SCHEMA_VERSION,
            "transport": self.transport,
            "actor": self.actor,
            "sourceSystem": self.source_system,
            "methods": list(SDK_METHODS),
        }

    def health(self) -> Dict[str, Any]:
        try:
            r = self._call("snapshotState", [])
            return {
                "ok": r.get("ok", False),
                "schemaVersion": paa_schema.PAYMENTS_SCHEMA_VERSION,
                "detail": "reachable" if r.get("ok") else r.get("error"),
            }
        except Exception as e:  # pragma: no cover
            return {"ok": False, "detail": str(e)}

    # ── Internal dispatch ───────────────────────────────────────────────────
    def _call(self, method: str, args: List[Any]) -> Dict[str, Any]:
        if method not in SDK_METHODS:
            return {"ok": False, "error": f"Unknown SDK method: {method}"}

        envelope = {
            "method": method,
            "args": args,
            "requestId": f"req_{uuid.uuid4().hex[:12]}",
            "schemaVersion": paa_schema.PAYMENTS_SCHEMA_VERSION,
            "actor": self.actor,
            "sourceSystem": self.source_system,
        }

        if self.transport == "django_local":
            return self._dispatch_django_local(method, args)
        if self.transport == "http":
            return self._dispatch_http(envelope)
        if self.transport == "callback":
            return self._dispatch_callback(envelope)
        return {"ok": False, "error": f"unknown transport: {self.transport}"}

    def _dispatch_django_local(self, method: str, args: List[Any]) -> Dict[str, Any]:
        # Lazy import so we don't force a Django dependency at import time
        try:
            from . import paa_service
        except Exception as e:
            return {"ok": False, "error": f"django_local transport unavailable: {e}"}
        fn = getattr(paa_service, method, None)
        if fn is None:
            return {"ok": False, "error": f"paa_service missing: {method}"}
        try:
            return {"ok": True, "data": fn(*args)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _dispatch_http(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Stdlib-only to avoid forcing requests as a dep
            from urllib import request as _req
            from urllib.error import URLError, HTTPError
        except Exception as e:  # pragma: no cover
            return {"ok": False, "error": f"urllib unavailable: {e}"}

        body = json.dumps(envelope).encode("utf-8")
        req = _req.Request(self.endpoint, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-PAA-Schema", paa_schema.PAYMENTS_SCHEMA_VERSION)
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        try:
            with _req.urlopen(req, timeout=self.request_timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as e:  # pragma: no cover
            return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
        except URLError as e:  # pragma: no cover
            return {"ok": False, "error": f"network error: {e.reason}"}

        try:
            parsed = json.loads(raw)
        except Exception:
            return {"ok": False, "error": f"invalid JSON: {raw[:200]}"}
        if isinstance(parsed, dict) and "ok" in parsed:
            return parsed
        return {"ok": True, "data": parsed}

    def _dispatch_callback(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        try:
            r = self.send(envelope)
            if isinstance(r, dict) and "ok" in r:
                return r
            return {"ok": True, "data": r}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# Convenience default
def create_bridge(**kwargs) -> PAABridge:
    """Factory mirroring sdk.js createPAABridge()."""
    return PAABridge(**kwargs)
