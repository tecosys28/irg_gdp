"""
Corpus Fund Views — bridge-delegated (gov_v3 v3.1 integration)
================================================================
Legacy endpoint shapes are preserved so the GDP wallet UI, heir-guide and
any existing API consumer continue to work unchanged. Internally every
call now flows through `payment_bridge.PAABridge`, which routes to the
canonical IRG Payment Autonomy module in irg_gov.

The local `CorpusFund`, `Deposit`, `Investment`, `Settlement` ORM models
are retained in `corpus/models.py` as a LEGACY MIRROR — they are written
to in parallel with the bridge for read-path compatibility, but the PAA
module is the source of truth. When you're ready to decommission the
mirror, delete these models and point the frontend at
`/api/paa/corpus-funds/` and `/api/paa/transactions/` directly.
"""
from decimal import Decimal

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.conf import settings

from .models import CorpusFund, Deposit, Investment, Settlement
from .serializers import (
    CorpusFundSerializer, DepositSerializer,
    InvestmentSerializer, SettlementSerializer,
)
from services.blockchain import BlockchainService

# Bridge-first integration
from payment_bridge import get_bridge

blockchain = BlockchainService()


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def _ensure_bridge_cf_for_jeweler(jeweler_profile, local_cf):
    """
    Upsert a Jeweler_CF in the PAA bridge for this jeweler. ID is stable
    on the jeweler profile id so retries are idempotent.
    """
    bridge = get_bridge()
    cf_id = f"cf_jeweler_{jeweler_profile.id}"
    existing = bridge.get_corpus_fund(cf_id)
    if existing.get("ok") and existing.get("data"):
        return cf_id
    currency = getattr(settings, "IRG_GDP_PRIMARY_CURRENCY", "INR")
    bridge.create_corpus_fund({
        "id": cf_id,
        "cfType": "Jeweler_CF",
        "name": f"Jeweler CF — {getattr(jeweler_profile, 'business_name', jeweler_profile.id)}",
        "countryCode": getattr(jeweler_profile, "country_code", "IN") or "IN",
        "ownerId": str(jeweler_profile.id),
        "primaryCurrency": currency,
        "isMultiCurrencyAccount": False,
        "bankName": getattr(jeweler_profile, "bank_name", "") or "",
        "balances": [
            {"currency": currency, "balance": float(local_cf.total_balance or 0),
             "lastUpdated": timezone.now().isoformat()},
        ],
    })
    return cf_id


def _extract_validation(result):
    """Normalise a bridge result's validation payload for legacy API."""
    if not isinstance(result, dict):
        return {"error": "unknown bridge response"}
    if "validation" in (result.get("data") or {}):
        return result["data"]["validation"]
    if "error" in result:
        return {"error": result["error"]}
    return {"error": "unspecified"}


# ─────────────────────────────────────────────────────────────────────────────
# CORPUS FUND VIEWSET
# ─────────────────────────────────────────────────────────────────────────────
class CorpusFundViewSet(viewsets.ModelViewSet):
    """
    Legacy surface area; reads return the local `CorpusFund` model shape
    alongside a `paa_bridge` field with the canonical PAA view. For the
    pure PAA view, hit `/api/paa/corpus-funds/`.
    """
    serializer_class = CorpusFundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, "jeweler_profile"):
            return CorpusFund.objects.filter(jeweler=self.request.user.jeweler_profile)
        return CorpusFund.objects.none()

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Fund summary with allocation breakdown (legacy shape + PAA view)."""
        fund = self.get_object()
        cfg = settings.IRG_GDP_CONFIG

        bridge_cf = None
        if hasattr(self.request.user, "jeweler_profile"):
            cf_id = _ensure_bridge_cf_for_jeweler(self.request.user.jeweler_profile, fund)
            bridge_cf = get_bridge().get_corpus_fund(cf_id).get("data")

        return Response({
            "fund": CorpusFundSerializer(fund).data,
            "allocation": {
                "physical_gold_percent": cfg["PHYSICAL_GOLD_PERCENT"],
                "physical_gold_value": str(fund.physical_gold_value),
                "other_investments_percent": cfg["OTHER_INVESTMENTS_PERCENT"],
                "other_investments_value": str(fund.other_investments_value),
            },
            "deposits": DepositSerializer(
                fund.deposits.filter(status="CONFIRMED").order_by("-deposited_at")[:10],
                many=True,
            ).data,
            "investments": InvestmentSerializer(
                fund.investments.filter(status="ACTIVE"), many=True,
            ).data,
            "paa_bridge": bridge_cf,
        })


# ─────────────────────────────────────────────────────────────────────────────
# DEPOSIT VIEWSET  — routes through the PAA bridge
# ─────────────────────────────────────────────────────────────────────────────
class DepositViewSet(viewsets.ModelViewSet):
    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]

    # GDP deposit_type → PAA category
    CATEGORY_MAP = {
        "MINTING":     "gdp_minting_cost",
        "JR_ISSUANCE": "tgdp_ftr_gic_jr_sale",
        "VOLUNTARY":   "other_collection",
        "PENALTY":     "default_compensation",
    }

    def get_queryset(self):
        return Deposit.objects.filter(depositor=self.request.user)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """
        Confirm a deposit. Legacy endpoint — shape preserved for backwards
        compatibility. Internally: posts a `collection` transaction to the
        canonical PAA via the bridge. The local `CorpusFund` and `Deposit`
        rows are mirrored after a successful PAA post.
        """
        deposit = self.get_object()
        if deposit.status != "PENDING":
            return Response({"error": "Deposit not pending"},
                            status=status.HTTP_400_BAD_REQUEST)

        fund = deposit.corpus_fund
        currency = getattr(settings, "IRG_GDP_PRIMARY_CURRENCY", "INR")

        cf_id = _ensure_bridge_cf_for_jeweler(fund.jeweler, fund)
        paa_category = self.CATEGORY_MAP.get(deposit.deposit_type, "other_collection")

        bridge = get_bridge()
        actor = getattr(request.user, "username", None) or "gdp.user"
        result = bridge.post_collection(
            category=paa_category,
            amount=float(deposit.amount),
            currency=currency,
            from_account=f"user:{request.user.id}",
            source_ref=f"gdp-deposit-{deposit.id}",
            notes=f"GDP deposit {deposit.deposit_type} for fund {fund.id}",
        )
        if not result.get("ok"):
            return Response({
                "error": "PAA rejected the deposit",
                "validation": _extract_validation(result),
            }, status=status.HTTP_400_BAD_REQUEST)

        paa_tx = result["data"]["transaction"]

        # Mirror into the legacy row.
        deposit.status = "CONFIRMED"
        deposit.deposit_tx_hash = paa_tx.get("blockchainTxHash") or ""
        deposit.confirmed_at = timezone.now()
        deposit.save()

        fund.total_balance = (fund.total_balance or Decimal(0)) + deposit.amount
        fund.save()

        return Response({
            **DepositSerializer(deposit).data,
            "paa_transaction_id": paa_tx["id"],
            "paa_status": paa_tx["status"],
            "actor": actor,
        })


# ─────────────────────────────────────────────────────────────────────────────
# SETTLEMENT VIEWSET — routes outflows through the PAA bridge
# ─────────────────────────────────────────────────────────────────────────────
class SettlementViewSet(viewsets.ModelViewSet):
    serializer_class = SettlementSerializer
    permission_classes = [IsAuthenticated]

    # GDP settlement_type → PAA category
    CATEGORY_MAP = {
        "BUYBACK":    "gdp_recovery",
        "BONUS":      "trust_beneficiary_income",
        "WITHDRAWAL": "other_payment",
    }

    def get_queryset(self):
        return Settlement.objects.filter(beneficiary=self.request.user)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def process_settlement(self, request):
        """
        Admin: process a corpus fund settlement. Rule validation, budget
        utilisation, corpus-ratio enforcement, and approval thresholds are
        all handled by the PAA bridge — this endpoint is now a thin proxy.
        """
        fund_id = request.data.get("fund_id")
        beneficiary_id = request.data.get("beneficiary_id")
        amount = Decimal(str(request.data.get("amount", 0)))
        settlement_type = request.data.get("settlement_type")
        reference_id = request.data.get("reference_id", "")

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            fund = CorpusFund.objects.get(id=fund_id)
            beneficiary = User.objects.get(id=beneficiary_id)
        except (CorpusFund.DoesNotExist, User.DoesNotExist):
            return Response({"error": "Fund or beneficiary not found"},
                            status=status.HTTP_404_NOT_FOUND)

        # Local fast-fail. The PAA engine does a stronger corpus-ratio check
        # that may also reject, but this gives a cheap early error.
        if fund.total_balance < amount:
            return Response({"error": "Insufficient fund balance"},
                            status=status.HTTP_400_BAD_REQUEST)

        currency = getattr(settings, "IRG_GDP_PRIMARY_CURRENCY", "INR")
        paa_category = self.CATEGORY_MAP.get(settlement_type, "other_payment")

        bridge = get_bridge()
        cf_id = _ensure_bridge_cf_for_jeweler(fund.jeweler, fund)

        result = bridge.request_payment(
            category=paa_category,
            amount=float(amount),
            currency=currency,
            from_account=cf_id,
            source_ref=f"gdp-settlement-{reference_id or timezone.now().isoformat()}",
            notes=f"GDP {settlement_type} settlement for beneficiary {beneficiary.id}",
        )
        if not result.get("ok"):
            return Response({
                "error": "PAA rejected the settlement",
                "validation": _extract_validation(result),
            }, status=status.HTTP_400_BAD_REQUEST)

        paa_tx = result["data"]["transaction"]

        settlement = Settlement.objects.create(
            corpus_fund=fund,
            beneficiary=beneficiary,
            settlement_type=settlement_type,
            amount=amount,
            reference_id=reference_id,
            settlement_tx_hash=paa_tx.get("blockchainTxHash") or "",
        )

        # NB: legacy mirror intentionally does NOT debit `fund.total_balance`
        # here — the PAA transaction is still pending approval. Downstream
        # reconciliation listens for PAA executed events and mirrors the
        # balance then. See integration guide: "Settlement lifecycle".

        return Response({
            **SettlementSerializer(settlement).data,
            "paa_transaction_id": paa_tx["id"],
            "paa_status": paa_tx["status"],
            "paa_required_approval": paa_tx.get("requiredApproval"),
        }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# INVESTMENT VIEWSET — unchanged (local-only, trustee-driven)
# ─────────────────────────────────────────────────────────────────────────────
class InvestmentViewSet(viewsets.ModelViewSet):
    """
    Trustee-banker investment tracking. Inflows (ROI proceeds) and
    outflows (liquidations) that reach the CF are posted to the PAA
    bridge via the deposit / settlement paths above.
    """
    serializer_class = InvestmentSerializer
    permission_classes = [IsAdminUser]
    queryset = Investment.objects.all()
