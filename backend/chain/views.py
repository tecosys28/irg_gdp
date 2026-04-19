"""
IRG Chain 888101 — Audit sink.

When the middleware successfully broadcasts a transaction it fires a
best-effort POST to AUDIT_SINK_URL so the DB has a second record of
the hash (in case the middleware's response to the original
/submit-tx caller was lost).

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import TxAuditLog

logger = logging.getLogger(__name__)


def _sink_token() -> str:
    return getattr(settings, 'BLOCKCHAIN_CONFIG', {}).get('AUDIT_SINK_TOKEN', '') or ''


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def audit_sink(request):
    """
    Internal callback from the middleware. Authenticated with a simple
    bearer token — the middleware and Django live on the same private
    network so mTLS is overkill for this hop.
    """
    token = _sink_token()
    if not token:
        return Response({'error': 'sink_disabled'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth != f'Bearer {token}':
        return Response({'error': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

    payload = request.data or {}
    client_tx_id = payload.get('clientTxId')
    tx_hash = payload.get('txHash')
    if not client_tx_id or not tx_hash:
        return Response({'error': 'bad_payload'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        audit = TxAuditLog.objects.get(client_tx_id=client_tx_id)
    except TxAuditLog.DoesNotExist:
        # Middleware saw a tx we have no record of. Create a defensive row
        # so the chain's view of the world is not lost.
        logger.warning('Audit sink received unknown clientTxId=%s — creating recovery row', client_tx_id)
        audit = TxAuditLog.objects.create(
            client_tx_id=client_tx_id,
            module=payload.get('module') or 'unknown',
            action=payload.get('action') or 'unknown',
            mode=payload.get('mode') or 'system',
            chain_id=int(payload.get('chainId') or 888101),
            meta=payload.get('meta') or {},
            status='SUBMITTED',
            tx_hash=tx_hash,
        )
        return Response({'ok': True, 'recovered': True})

    # Happy path: update the row only if we didn't already record a hash.
    changed = False
    if not audit.tx_hash:
        audit.tx_hash = tx_hash
        changed = True
    if audit.status == 'PENDING':
        audit.status = 'SUBMITTED'
        changed = True
    if changed:
        audit.save(update_fields=['tx_hash', 'status', 'updated_at'])
    return Response({'ok': True})
