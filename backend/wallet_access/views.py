"""
IRG Chain 888101 — Wallet access REST endpoints.

Thin views around the service layer. All errors flow through a single
handler that turns `WalletAccessError` subclasses into structured 4xx
responses.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from dataclasses import asdict

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from chain.models import TxAuditLog

from . import services
from .models import NomineeRegistration, RecoveryCase, WalletActivation, WalletDevice


def _error_response(exc: services.WalletAccessError, status_code: int = 400):
    return Response(
        {'error': str(exc), 'code': getattr(exc, 'code', 'wallet_access_error')},
        status=status_code,
    )


# ─── INFO / STATUS ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_info(request):
    try:
        info = services.get_wallet_info(request.user)
    except services.WalletAccessError as exc:
        return _error_response(exc, 404)
    return Response(asdict(info))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_status_banner(request):
    """
    Lightweight endpoint the frontend polls to drive the activation banner.
    Returns a banner spec or nothing.
    """
    wallet = getattr(request.user, 'wallet_activation', None)
    if wallet is None:
        return Response({'banner': None})

    if wallet.state == 'CREATED':
        return Response({'banner': {
            'level': 'warning',
            'message': 'Your wallet is not yet activated. Set your wallet password and register nominees before you can transact.',
            'cta_label': 'Activate Wallet',
            'cta_route': '/wallet/activate',
        }})
    if wallet.state == 'LOCKED':
        return Response({'banner': {
            'level': 'danger',
            'message': 'Your wallet is locked due to repeated failed password attempts.',
            'cta_label': 'Unlock',
            'cta_route': '/wallet/unlock',
        }})
    if wallet.state == 'RECOVERING':
        return Response({'banner': {
            'level': 'danger',
            'message': 'A recovery is in progress on your wallet. If this was not you, cancel immediately.',
            'cta_label': 'Review Recovery',
            'cta_route': '/wallet/recovery',
        }})
    if wallet.state == 'SUSPENDED':
        return Response({'banner': {
            'level': 'danger',
            'message': 'Your wallet is suspended. Contact support.',
            'cta_label': 'Contact Support',
            'cta_route': '/support',
        }})
    if wallet.state == 'RECOVERED':
        return Response({'banner': {
            'level': 'info',
            'message': 'This wallet has been recovered to another address.',
            'cta_label': None,
            'cta_route': None,
        }})

    # Activated — check for policy-driven banners
    active = wallet.nominees.filter(active=True).count()
    if active < 2:
        return Response({'banner': {
            'level': 'warning',
            'message': 'Register at least two nominees to protect your assets.',
            'cta_label': 'Manage Nominees',
            'cta_route': '/wallet/nominees',
        }})
    return Response({'banner': None})


# ─── ACTIVATION ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate(request):
    """
    Body:
      {
        "wallet_password": "...",
        "seed_phrase_words": ["w1", ..., "w15"],
        "holder_type": "INDIVIDUAL" | "LEGAL_PERSON",
        "legal_entity_name": "...",          # required if LEGAL_PERSON
        "entity_type": "PRIVATE_LTD" | ...,  # required if LEGAL_PERSON
        "nominees": [...],                   # required for INDIVIDUAL
        "device_id_hash": "0x...",
        "device_label": "iPhone 14",
        "platform": "ios",
        "terms_accepted": true
      }
    """
    data = request.data or {}
    try:
        info = services.activate_wallet(
            request.user,
            wallet_password=data.get('wallet_password', ''),
            seed_phrase_words=data.get('seed_phrase_words') or [],
            holder_type=data.get('holder_type', 'INDIVIDUAL'),
            legal_entity_name=data.get('legal_entity_name', ''),
            entity_type=data.get('entity_type', ''),
            nominees=data.get('nominees') or [],
            device_id_hash=data.get('device_id_hash', ''),
            device_label=data.get('device_label', ''),
            platform=data.get('platform', ''),
            terms_accepted=bool(data.get('terms_accepted')),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc, 400)
    return Response(asdict(info))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    data = request.data or {}
    try:
        services.change_wallet_password(
            request.user,
            old_password=data.get('old_password', ''),
            new_password=data.get('new_password', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_password(request):
    """Confirm the user knows their wallet password (used as a pre-sign step)."""
    try:
        ok = services.verify_wallet_password(request.user, request.data.get('password', ''))
    except services.WalletAccessError as exc:
        return _error_response(exc, 423 if exc.code == 'wallet_locked' else 400)
    return Response({'verified': ok})


# ─── NOMINEES ───────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_nominees(request):
    wallet = getattr(request.user, 'wallet_activation', None)
    if wallet is None:
        return Response([], status=200)
    rows = [
        {
            'id': n.id,
            'name': n.name,
            'relationship': n.relationship,
            'email': n.email,
            'mobile': n.mobile,
            'share_percent': str(n.share_percent),
            'social_recovery_threshold': n.social_recovery_threshold,
            'active': n.active,
        }
        for n in wallet.nominees.filter(active=True)
    ]
    return Response(rows)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_nominees(request):
    data = request.data or {}
    try:
        services.update_nominees(
            request.user,
            nominees=data.get('nominees') or [],
            wallet_password=data.get('wallet_password', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'ok': True})


# ─── DEVICES ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_devices(request):
    wallet = getattr(request.user, 'wallet_activation', None)
    if wallet is None:
        return Response([], status=200)
    rows = [
        {
            'id': d.id,
            'device_id_hash': d.device_id_hash,
            'device_label': d.device_label,
            'platform': d.platform,
            'state': d.state,
            'cooling_off_until': d.cooling_off_until.isoformat() if d.cooling_off_until else None,
            'bound_at': d.bound_at.isoformat(),
            'activated_at': d.activated_at.isoformat() if d.activated_at else None,
            'retired_at': d.retired_at.isoformat() if d.retired_at else None,
        }
        for d in wallet.devices.all().order_by('-bound_at')
    ]
    return Response(rows)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bind_device(request):
    data = request.data or {}
    try:
        device = services.bind_new_device(
            request.user,
            device_id_hash=data.get('device_id_hash', ''),
            device_label=data.get('device_label', ''),
            platform=data.get('platform', ''),
            wallet_password=data.get('wallet_password', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'id': device.id, 'cooling_off_until': device.cooling_off_until.isoformat()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_device(request):
    data = request.data or {}
    try:
        services.revoke_device(
            request.user,
            device_id=int(data.get('device_id') or 0),
            wallet_password=data.get('wallet_password', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'ok': True})


# ─── EMERGENCY FREEZE ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emergency_freeze(request):
    try:
        services.emergency_freeze(request.user, reason=request.data.get('reason', ''))
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'ok': True})


# ─── INACTIVITY ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_liveness(request):
    """
    User taps "Confirm I am active" in response to an inactivity prompt.
    Also called implicitly on login (see the login signal handler).
    """
    try:
        ev = services.confirm_liveness(request.user)
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({
        'id': ev.id,
        'kind': ev.kind,
        'occurred_at': ev.occurred_at.isoformat(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def liveness_history(request):
    """Inactivity audit trail for this wallet."""
    wallet = getattr(request.user, 'wallet_activation', None)
    if wallet is None:
        return Response([])
    return Response([
        {
            'id': e.id,
            'kind': e.kind,
            'occurred_at': e.occurred_at.isoformat(),
            'detail': e.detail,
        }
        for e in wallet.inactivity_events.all()[:40]
    ])


# ─── OWNERSHIP TRANSFER (legal-person wallets) ──────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_ownership_transfer(request):
    data = request.data or {}
    try:
        case = services.initiate_ownership_transfer(
            outgoing_user=request.user,
            incoming_user_id=data.get('incoming_user_id'),
            reason=data.get('reason', ''),
            grounds=data.get('grounds', ''),
            evidence_bundle_hash=data.get('evidence_bundle_hash', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({
        'case_id': case.id,
        'status': case.status,
        'public_notice_ends_at': case.public_notice_ends_at.isoformat() if case.public_notice_ends_at else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_ownership_transfer_view(request):
    data = request.data or {}
    try:
        case = services.cancel_ownership_transfer(
            request.user,
            case_id=int(data.get('case_id') or 0),
            reason=data.get('reason', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'case_id': case.id, 'status': case.status})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_ownership_transfers(request):
    wallet = getattr(request.user, 'wallet_activation', None)
    if wallet is None:
        return Response([])
    rows = [
        {
            'id': c.id,
            'status': c.status,
            'reason': c.reason,
            'grounds': c.grounds[:500],
            'public_notice_ends_at': c.public_notice_ends_at.isoformat() if c.public_notice_ends_at else None,
            'transfer_requested_tx_hash': c.transfer_requested_tx_hash,
            'ombudsman_order_hash': c.ombudsman_order_hash,
            'created_at': c.created_at.isoformat(),
        }
        for c in wallet.ownership_transfers.all()[:50]
    ]
    return Response(rows)


# ─── CSV EXPORT ─────────────────────────────────────────────────────────────

from django.http import HttpResponse  # noqa: E402

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_history_csv(request):
    csv_text = services.transactions_to_csv(
        request.user,
        module=request.GET.get('module', ''),
        status_filter=request.GET.get('status', ''),
    )
    resp = HttpResponse(csv_text, content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="irg_transactions.csv"'
    return resp


# ─── RECOVERY ───────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def recover_self(request):
    """
    New device + seed phrase. Auto-approves on seed match.
    """
    data = request.data or {}
    try:
        case = services.initiate_self_recovery(
            request.user,
            seed_phrase_words=data.get('seed_phrase_words') or [],
            new_device_id_hash=data.get('new_device_id_hash', ''),
            new_device_label=data.get('new_device_label', ''),
            new_platform=data.get('new_platform', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'case_id': case.id, 'status': case.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def recover_social(request):
    data = request.data or {}
    try:
        case = services.initiate_social_recovery(
            claimant_user=request.user,
            original_wallet_address=data.get('original_wallet_address', ''),
            claimant_wallet_address=data.get('claimant_wallet_address', ''),
            grounds=data.get('grounds', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({
        'case_id': case.id,
        'status': case.status,
        'cooling_off_ends_at': case.cooling_off_ends_at.isoformat() if case.cooling_off_ends_at else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def recover_trustee(request):
    data = request.data or {}
    try:
        case = services.initiate_trustee_recovery(
            claimant_user=request.user,
            original_wallet_address=data.get('original_wallet_address', ''),
            claimant_wallet_address=data.get('claimant_wallet_address', ''),
            grounds=data.get('grounds', ''),
            evidence_bundle_hash=data.get('evidence_bundle_hash', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({
        'case_id': case.id,
        'status': case.status,
        'recovery_requested_tx_hash': case.recovery_requested_tx_hash,
        'public_notice_ends_at': case.public_notice_ends_at.isoformat() if case.public_notice_ends_at else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_recovery_view(request):
    data = request.data or {}
    try:
        case = services.cancel_recovery(
            request.user,
            case_id=int(data.get('case_id') or 0),
            reason=data.get('reason', ''),
        )
    except services.WalletAccessError as exc:
        return _error_response(exc)
    return Response({'case_id': case.id, 'status': case.status})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_recovery_cases(request):
    wallet = getattr(request.user, 'wallet_activation', None)
    if wallet is None:
        return Response([])
    rows = [
        {
            'id': c.id,
            'path': c.path,
            'status': c.status,
            'claimant_wallet_address': c.claimant_wallet_address,
            'grounds': c.grounds[:500],
            'cooling_off_ends_at': c.cooling_off_ends_at.isoformat() if c.cooling_off_ends_at else None,
            'public_notice_ends_at': c.public_notice_ends_at.isoformat() if c.public_notice_ends_at else None,
            'execution_tx_hash': c.execution_tx_hash,
            'reversibility_ends_at': c.reversibility_ends_at.isoformat() if c.reversibility_ends_at else None,
            'created_at': c.created_at.isoformat(),
        }
        for c in wallet.recovery_cases.order_by('-created_at')[:50]
    ]
    return Response(rows)


# ─── TRANSACTION HISTORY (reports) ──────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    """
    Filtered view of chain_tx_audit_log for the caller. Supports query
    params: module, action, status, limit (default 50, max 200).
    """
    limit = min(int(request.GET.get('limit') or 50), 200)
    qs = TxAuditLog.objects.filter(actor=request.user).order_by('-created_at')

    if request.GET.get('module'):
        qs = qs.filter(module=request.GET['module'])
    if request.GET.get('action'):
        qs = qs.filter(action=request.GET['action'])
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'])

    rows = [
        {
            'id': r.id,
            'client_tx_id': r.client_tx_id,
            'module': r.module,
            'action': r.action,
            'mode': r.mode,
            'chain_id': r.chain_id,
            'to_address': r.to_address,
            'tx_hash': r.tx_hash,
            'block_number': r.block_number,
            'status': r.status,
            'created_at': r.created_at.isoformat(),
            'confirmed_at': r.confirmed_at.isoformat() if r.confirmed_at else None,
            'meta': r.meta,
        }
        for r in qs[:limit]
    ]
    return Response(rows)


# ─── HEIR GUIDE (public, no login) ──────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def heir_guide(request):
    """
    Public-facing guide for family members of a deceased or incapacitated
    wallet owner. Accessible without login so a grieving family that has
    never seen this app can find instructions.
    """
    return Response({
        'title': 'How to recover an IRG wallet for a family member',
        'intro': (
            'If someone you love held assets in an IRG wallet and has passed away, '
            'become incapacitated, or lost access in a way that cannot be resolved, '
            'this guide explains how to claim those assets on their behalf.'
        ),
        'steps': [
            {
                'heading': '1. Gather documentation',
                'body': (
                    'Depending on the situation, you may need: death certificate, '
                    'succession certificate or legal heir certificate, court-issued '
                    'letter of administration, a registered nominee document, or a '
                    'probated will.'
                ),
            },
            {
                'heading': '2. File a trustee-path recovery case',
                'body': (
                    'From the IRG login screen, choose "Recover Someone Else\'s Wallet". '
                    'You will be asked for the wallet address (if known), your relationship, '
                    'and to upload supporting documents.'
                ),
            },
            {
                'heading': '3. Public notice period',
                'body': (
                    'For 30 days a public on-chain notice will be posted so any other '
                    'claimant or objection can be heard. The original wallet holder (if alive) '
                    'will also be notified repeatedly.'
                ),
            },
            {
                'heading': '4. Ombudsman review',
                'body': (
                    'The IRG Ombudsman will review the file, may hold a hearing, '
                    'and will issue a reasoned Order. Hearings can be in-person, by video, '
                    'or in writing.'
                ),
            },
            {
                'heading': '5. Execution',
                'body': (
                    'If the Ombudsman approves, assets transfer to the wallet you control. '
                    'A 90-day reversibility window applies in case a civil court '
                    'subsequently rules differently.'
                ),
            },
        ],
        'contact': 'For help with any step, contact the IRG Ombudsman office via the "Recovery" menu item.',
    })
