"""Smoke test for the Python PAA bridge — validates schema parity, transport
dispatch, idempotency key stability, and the callback transport. Django is
mocked out so this runs in any Python 3 environment."""
import sys, os, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.resolve()))

# Quarantine Django so paa_service doesn't get imported.
class _Stub:
    def __getattr__(self, _):  # pragma: no cover
        raise ImportError("django stub — paa_service should not be touched in callback mode")
sys.modules.setdefault("django", _Stub())
sys.modules.setdefault("django.db", _Stub())
sys.modules.setdefault("django.utils", _Stub())
sys.modules.setdefault("django.conf", _Stub())

from payment_bridge import paa_schema
from payment_bridge.bridge import PAABridge, SDK_METHODS

pass_, fail = 0, 0
def t(name, cond, detail=""):
    global pass_, fail
    if cond:
        pass_ += 1; print(f"  ✓  {name}")
    else:
        fail += 1; print(f"  ✗  {name}{'  ::  ' + detail if detail else ''}")

print("\n=== schema parity ===")
t("schema version 1.0.0", paa_schema.PAYMENTS_SCHEMA_VERSION == "1.0.0")
t("10 supported currencies", len(paa_schema.SUPPORTED_CURRENCIES) == 10)
t("29 categories", len(paa_schema.TRANSACTION_CATEGORIES) == 29)
t("4 CF types", len(paa_schema.CORPUS_FUND_TYPES) == 4)
t("super corpus = IRG_CF", paa_schema.SUPER_CORPUS_FUND_TYPE == "IRG_CF")

print("\n=== routing ===")
t("license_fee → IRG_CF",      paa_schema.get_routing_for("license_fee") == "IRG_CF")
t("irg_gdp_sale → Jeweler_CF", paa_schema.get_routing_for("irg_gdp_sale") == "Jeweler_CF")
t("irg_ftr_sale → Minter_CF",  paa_schema.get_routing_for("irg_ftr_sale") == "Minter_CF")
t("dac_charges → IRG_Local_CF",paa_schema.get_routing_for("dac_charges") == "IRG_Local_CF")

print("\n=== approval levels ===")
t("$5 → single",       paa_schema.get_approval_level_for(5) == "single")
t("$5000 → dual",      paa_schema.get_approval_level_for(5_000) == "dual")
t("$50000 → board",    paa_schema.get_approval_level_for(50_000) == "board")
t("$2M → court",       paa_schema.get_approval_level_for(2_000_000) == "court")

print("\n=== FX ===")
t("USD rate 1.0", paa_schema.get_usd_rate("USD") == 1.0)
t("INR to USD", abs(paa_schema.to_usd(100_000, "INR") - 1200.0) < 0.01)
t("EUR to INR roundtrip",
  abs(paa_schema.convert(paa_schema.convert(1000, "EUR", "INR"), "INR", "EUR") - 1000) < 0.01)

print("\n=== idempotency key stability ===")
k1 = paa_schema.make_idempotency_key("gdp", "ref-123", "license_fee", 500, "USD")
k2 = paa_schema.make_idempotency_key("gdp", "ref-123", "license_fee", 500, "USD")
k3 = paa_schema.make_idempotency_key("gdp", "ref-124", "license_fee", 500, "USD")
t("same inputs → same key", k1 == k2)
t("different ref → different key", k1 != k3)

print("\n=== method allow-list parity with sdk.js ===")
expected = {
    "listCorpusFunds", "getCorpusFund", "getSuperCorpus", "totalCorpusValueUSD",
    "listTransactions", "getTransaction",
    "getActiveBudget", "listTrustees", "getTrustee",
    "getAuditLog", "getDashboardMetrics", "snapshotState",
    "createTransaction", "approveTransaction", "executeTransaction",
    "cancelTransaction", "recordOracleConfirmation",
    "createCorpusFund", "proposeBudget", "voteOnRuleChange",
    "applyApprovedRuleChange", "uploadCourtApproval",
    "registerTrustee", "scoreTrustee",
}
t("22 methods exposed", set(SDK_METHODS) == expected)

print("\n=== PAABridge callback transport ===")
calls = []
def send(env):
    calls.append(env)
    if env["method"] == "getSuperCorpus":
        return {"ok": True, "data": {"id": "cf_irg_super", "cfType": "IRG_CF"}}
    if env["method"] == "createTransaction":
        return {"ok": True, "data": {"transaction": {"id": "tx_stub", "status": "approved"}}}
    return {"ok": False, "error": "unhandled"}

b = PAABridge(transport="callback", send=send, actor="tester", source_system="smoke")
t("meta schema version matches", b.meta()["schemaVersion"] == paa_schema.PAYMENTS_SCHEMA_VERSION)

r = b.get_super_corpus()
t("get_super_corpus ok", r["ok"] and r["data"]["cfType"] == "IRG_CF")
t("envelope wire shape", calls[-1]["method"] == "getSuperCorpus"
                         and calls[-1]["schemaVersion"] == "1.0.0"
                         and calls[-1]["sourceSystem"] == "smoke")

r2 = b.post_collection(category="license_fee", amount=100, currency="USD",
                       from_account="user:42", source_ref="smoke-001")
t("post_collection routes through createTransaction", calls[-1]["method"] == "createTransaction")
t("idempotency key passed through",
  calls[-1]["args"][0]["idempotencyKey"] == paa_schema.make_idempotency_key(
      "smoke", "smoke-001", "license_fee", 100, "USD"))
t("post_collection returned ok", r2["ok"])

print("\n=== version mismatch guard ===")
err = None
try:
    PAABridge(transport="callback", send=send, expect_schema_version="99.0.0")
except Exception as e:
    err = e
t("constructor rejects mismatched pin", err is not None)

print(f"\n=== summary ===")
print(f"  {pass_} passed, {fail} failed.")
sys.exit(1 if fail else 0)
