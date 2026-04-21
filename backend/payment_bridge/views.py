"""
IRG PAA Bridge — HTTP views

Exposes the canonical PAA API at /api/paa/... for:
  * The GDP frontend (wallet.html, heir-guide.html)
  * Any external IRG service that wants to speak to GDP's local bridge
  * The gov_v3 proxy when running in hybrid mode

Every endpoint is a thin wrapper around bridge.PAABridge — which means the
same URL path returns the same shape whether the bridge is running in
django_local mode (today) or proxies to gov_v3 via HTTP (tomorrow).
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from . import get_bridge, paa_schema


# ─────────────────────────────────────────────────────────────────────────────
# Corpus funds
# ─────────────────────────────────────────────────────────────────────────────
class CorpusFundViewSet(viewsets.ViewSet):
    """Read-only view onto the PAA corpus fund registry."""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        bridge = get_bridge()
        result = bridge.list_corpus_funds({
            "cfType":      request.query_params.get("cfType"),
            "ownerId":     request.query_params.get("ownerId"),
            "countryCode": request.query_params.get("countryCode"),
        })
        return Response(result)

    def retrieve(self, request, pk=None):
        result = get_bridge().get_corpus_fund(pk)
        if not result.get("ok") or result.get("data") is None:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)

    @action(detail=False, methods=["get"])
    def super_corpus(self, request):
        return Response(get_bridge().get_super_corpus())

    @action(detail=False, methods=["get"])
    def total_usd(self, request):
        return Response(get_bridge().total_corpus_value_usd())


# ─────────────────────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────────────────────
class PaaTransactionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        bridge = get_bridge()
        filter_ = {
            "status":   request.query_params.get("status"),
            "cfType":   request.query_params.get("cfType"),
            "category": request.query_params.get("category"),
            "sourceSystem": request.query_params.get("sourceSystem"),
        }
        filter_ = {k: v for k, v in filter_.items() if v}
        return Response(bridge.list_transactions(filter_))

    def retrieve(self, request, pk=None):
        return Response(get_bridge().get_transaction(pk))

    def create(self, request):
        actor = getattr(request.user, "username", "anon") or "anon"
        return Response(
            get_bridge().create_transaction(request.data, actor=actor),
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        actor = getattr(request.user, "username", "anon") or "anon"
        role = request.data.get("role", "AdvisoryBoardMember")
        return Response(get_bridge().approve_transaction(pk, actor=actor, role=role))

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        actor = getattr(request.user, "username", "anon") or "anon"
        return Response(get_bridge().execute_transaction(pk, actor=actor))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        actor = getattr(request.user, "username", "anon") or "anon"
        reason = request.data.get("reason", "")
        return Response(get_bridge().cancel_transaction(pk, actor=actor, reason=reason))

    @action(detail=True, methods=["post"], url_path="oracle/(?P<oracle_type>[a-z_]+)")
    def confirm_oracle(self, request, pk=None, oracle_type=None):
        actor = getattr(request.user, "username", "anon") or "anon"
        doc_hash = request.data.get("documentHash")
        return Response(get_bridge().record_oracle_confirmation(
            pk, oracle_type, actor=actor, document_hash=doc_hash,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Budget / trustees / audit
# ─────────────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_budget(request):
    return Response(get_bridge().get_active_budget())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    return Response(get_bridge().get_dashboard_metrics())


@api_view(["GET"])
@permission_classes([IsAdminUser])
def audit_log(request):
    f = {
        "action": request.query_params.get("action"),
        "actor":  request.query_params.get("actor"),
    }
    f = {k: v for k, v in f.items() if v}
    return Response(get_bridge().get_audit_log(f))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bridge_meta(request):
    return Response(get_bridge().meta())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bridge_health(request):
    return Response(get_bridge().health())


# ─────────────────────────────────────────────────────────────────────────────
# Generic RPC handler — mirrors sdk.js buildHTTPHandler so cross-system
# consumers (FTR/DAC) can POST the SDK envelope format directly.
# ─────────────────────────────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rpc(request):
    payload = request.data or {}
    client_version = payload.get("schemaVersion")
    if client_version and client_version != paa_schema.PAYMENTS_SCHEMA_VERSION:
        return Response(
            {"ok": False, "error":
             f"schema version mismatch: server {paa_schema.PAYMENTS_SCHEMA_VERSION}, "
             f"client {client_version}"},
            status=status.HTTP_409_CONFLICT,
        )
    method = payload.get("method")
    args = payload.get("args") or []

    # Normalise camelCase → snake_case for PAABridge method names.
    snake = "".join("_" + c.lower() if c.isupper() else c for c in (method or ""))
    if snake.startswith("_"):
        snake = snake[1:]

    bridge = get_bridge()
    fn = getattr(bridge, snake, None)
    if fn is None:
        return Response({"ok": False, "error": f"method not allowed: {method}"},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        result = fn(*args)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # The bridge already returns { ok, data|error } envelopes — pass through.
    if isinstance(result, dict) and "ok" in result:
        return Response(result)
    return Response({"ok": True, "data": result})


# ─────────────────────────────────────────────────────────────────────────────
# Razorpay payment gateway
# ─────────────────────────────────────────────────────────────────────────────

def _razorpay_client():
    import razorpay
    from django.conf import settings
    key = settings.RAZORPAY_KEY_ID
    secret = settings.RAZORPAY_KEY_SECRET
    if not key or not secret:
        raise ValueError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not configured in environment.")
    return razorpay.Client(auth=(key, secret))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def razorpay_create_order(request):
    """
    Create a Razorpay order.
    Body: { amount_paise: int, purpose: str, reference_id: str (optional) }
    Returns: { order_id, amount, currency, key_id }
    """
    from django.conf import settings
    amount_paise = int(request.data.get("amount_paise", 0))
    if amount_paise <= 0:
        return Response({"error": "amount_paise must be > 0"}, status=status.HTTP_400_BAD_REQUEST)

    purpose      = request.data.get("purpose", "IRG_GDP Payment")
    reference_id = request.data.get("reference_id", "")

    try:
        client = _razorpay_client()
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        order = client.order.create({
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  (reference_id or str(request.user.id))[:40],
            "notes":    {"purpose": purpose, "user": str(request.user.email)},
        })
    except Exception as exc:
        return Response({"error": f"Razorpay error: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

    return Response({
        "order_id": order["id"],
        "amount":   order["amount"],
        "currency": order["currency"],
        "key_id":   settings.RAZORPAY_KEY_ID,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def razorpay_verify(request):
    """
    Verify a completed Razorpay payment.
    Body: { razorpay_order_id, razorpay_payment_id, razorpay_signature }
    Returns: { verified: true } or 400
    """
    import hmac, hashlib
    from django.conf import settings

    order_id   = request.data.get("razorpay_order_id", "")
    payment_id = request.data.get("razorpay_payment_id", "")
    signature  = request.data.get("razorpay_signature", "")

    if not all([order_id, payment_id, signature]):
        return Response({"error": "Missing payment fields"}, status=status.HTTP_400_BAD_REQUEST)

    msg = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return Response({"error": "Payment signature mismatch — possible tampering"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"verified": True, "payment_id": payment_id, "order_id": order_id})
