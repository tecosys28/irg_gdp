"""
IRG Chain 888101 — Django-side submission client.

This is the ONE module every GDP app calls when it wants to record a
transaction on-chain. It wraps the HTTP middleware with:

  * HMAC-signed requests (shared secret with middleware)
  * DB-first audit (we write a PENDING row BEFORE calling out, so a crash
    between "sent" and "stored" still leaves a trace)
  * Automatic retry with exponential backoff
  * Graceful degradation: if the middleware is unreachable AND
    IRG_CHAIN_ALLOW_SIMULATE is true, the call returns a deterministic
    simulated hash and records the row as SIMULATED so dev/CI still work

Callers never construct HTTP bodies themselves — they use the convenience
methods at the bottom of the file (system_submit / raw_submit).

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
from django.conf import settings
from django.db import transaction as db_transaction

from .models import TxAuditLog

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _cfg(key: str, default=None):
    """Pull a key out of settings.BLOCKCHAIN_CONFIG with a fallback."""
    return getattr(settings, 'BLOCKCHAIN_CONFIG', {}).get(key, default)


def _chain_id() -> int:
    return int(_cfg('CHAIN_ID', 888101))


def _middleware_url() -> str:
    # e.g. http://irg-middleware.irg-chain.svc.cluster.local:3100
    return (_cfg('MIDDLEWARE_URL', '') or '').rstrip('/')


def _shared_secret() -> str:
    return _cfg('MIDDLEWARE_SHARED_SECRET', '') or ''


def _allow_simulate() -> bool:
    return bool(_cfg('ALLOW_SIMULATE', settings.DEBUG))


def _timeout_seconds() -> float:
    return float(_cfg('SUBMIT_TIMEOUT_SECONDS', 15))


def _max_retries() -> int:
    return int(_cfg('SUBMIT_MAX_RETRIES', 3))


# ─────────────────────────────────────────────────────────────────────────────
# PAYLOAD TYPES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SubmitResult:
    """Uniform return value for every call site."""
    tx_hash: str
    chain_id: int
    status: str                      # SUBMITTED | SIMULATED | FAILED
    client_tx_id: str
    simulated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'tx_hash': self.tx_hash,
            'chain_id': self.chain_id,
            'status': self.status,
            'client_tx_id': self.client_tx_id,
            'simulated': self.simulated,
            'error': self.error,
        }


@dataclass
class SystemTx:
    """A transaction the backend originates and the middleware signs."""
    module: str
    action: str
    to_address: str
    data: str = '0x'
    value_wei: str = '0'
    meta: dict = field(default_factory=dict)
    actor_id: Optional[int] = None   # core.User.id of the triggering user, if any


@dataclass
class RawTx:
    """A transaction the user signed on their device; we only forward it."""
    module: str
    action: str
    signed_tx: str
    meta: dict = field(default_factory=dict)
    actor_id: Optional[int] = None
    # Optional hint fields for the audit log (not validated)
    to_address: str = ''
    value_wei: str = '0'


# ─────────────────────────────────────────────────────────────────────────────
# HMAC SIGNING
# ─────────────────────────────────────────────────────────────────────────────

def _sign_request(body_dict: dict) -> tuple[str, str, str]:
    """Return (body_json, timestamp, hex_hmac). Matches middleware verifyHmac()."""
    timestamp = str(int(time.time() * 1000))
    body_json = json.dumps(body_dict, separators=(',', ':'), sort_keys=False)
    msg = f'{timestamp}.{body_json}'
    digest = hmac.new(
        _shared_secret().encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return body_json, timestamp, digest


# ─────────────────────────────────────────────────────────────────────────────
# CORE SUBMIT
# ─────────────────────────────────────────────────────────────────────────────

def _new_client_tx_id(module: str, action: str) -> str:
    # Short enough to index, long enough to be unique across nodes.
    return f'{module}.{action}.{uuid.uuid4().hex[:20]}'


def _calldata_hash(data: str) -> str:
    if not data or data == '0x':
        return ''
    raw = data[2:] if data.startswith('0x') else data
    try:
        blob = bytes.fromhex(raw)
    except ValueError:
        blob = data.encode('utf-8')
    return '0x' + hashlib.sha256(blob).hexdigest()


def _simulated_hash(client_tx_id: str) -> str:
    return '0x' + hashlib.sha256(f'sim:{client_tx_id}'.encode()).hexdigest()


def _post_to_middleware(body: dict) -> tuple[int, dict]:
    url = f'{_middleware_url()}/submit-tx'
    body_json, timestamp, signature = _sign_request(body)
    headers = {
        'Content-Type': 'application/json',
        'X-IRG-Timestamp': timestamp,
        'X-IRG-Signature': signature,
    }
    resp = requests.post(url, data=body_json, headers=headers, timeout=_timeout_seconds())
    try:
        payload = resp.json()
    except ValueError:
        payload = {'success': False, 'error': f'non_json_response_{resp.status_code}'}
    return resp.status_code, payload


def _submit_with_retries(audit: TxAuditLog, body: dict) -> SubmitResult:
    """Retry loop. Updates audit row in-place."""
    attempts = _max_retries()
    delay = 0.5

    for attempt in range(1, attempts + 1):
        try:
            status_code, payload = _post_to_middleware(body)
            if status_code == 200 and payload.get('success'):
                audit.tx_hash = payload.get('txHash') or ''
                audit.chain_id = int(payload.get('chainId', _chain_id()))
                audit.status = 'SUBMITTED'
                audit.retries = attempt - 1
                audit.last_error = ''
                audit.save(update_fields=['tx_hash', 'chain_id', 'status', 'retries', 'last_error', 'updated_at'])
                return SubmitResult(
                    tx_hash=audit.tx_hash,
                    chain_id=audit.chain_id,
                    status='SUBMITTED',
                    client_tx_id=audit.client_tx_id,
                )
            # Non-200 or success=false — log and maybe retry
            err = payload.get('error') or f'http_{status_code}'
            logger.warning(
                'Middleware rejected tx (attempt %d/%d) module=%s action=%s err=%s',
                attempt, attempts, audit.module, audit.action, err,
            )
            audit.last_error = err[:500]
            # 4xx (other than 429) is usually a client bug; don't hammer the middleware
            if 400 <= status_code < 500 and status_code != 429:
                break
        except requests.RequestException as exc:
            logger.warning(
                'Middleware unreachable (attempt %d/%d) module=%s action=%s err=%s',
                attempt, attempts, audit.module, audit.action, exc,
            )
            audit.last_error = str(exc)[:500]

        if attempt < attempts:
            time.sleep(delay)
            delay = min(delay * 2, 4.0)

    # All attempts exhausted
    if _allow_simulate():
        sim_hash = _simulated_hash(audit.client_tx_id)
        audit.tx_hash = sim_hash
        audit.status = 'SIMULATED'
        audit.retries = attempts
        audit.save(update_fields=['tx_hash', 'status', 'retries', 'last_error', 'updated_at'])
        logger.info('Middleware unavailable — falling back to simulated hash for %s', audit.client_tx_id)
        return SubmitResult(
            tx_hash=sim_hash,
            chain_id=audit.chain_id,
            status='SIMULATED',
            client_tx_id=audit.client_tx_id,
            simulated=True,
            error=audit.last_error,
        )

    audit.status = 'FAILED'
    audit.retries = attempts
    audit.save(update_fields=['status', 'retries', 'last_error', 'updated_at'])
    return SubmitResult(
        tx_hash='',
        chain_id=audit.chain_id,
        status='FAILED',
        client_tx_id=audit.client_tx_id,
        error=audit.last_error,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def system_submit(tx: SystemTx) -> SubmitResult:
    """
    Backend-originated transaction. The middleware's SYSTEM_SIGNER_KEY signs
    and pays gas. Used for corpus settlements, oracle updates, recall,
    governance execution, dispute resolutions, etc.
    """
    client_tx_id = _new_client_tx_id(tx.module, tx.action)

    with db_transaction.atomic():
        audit = TxAuditLog.objects.create(
            client_tx_id=client_tx_id,
            module=tx.module,
            action=tx.action,
            mode='system',
            actor_id=tx.actor_id,
            chain_id=_chain_id(),
            to_address=tx.to_address,
            value_wei=str(tx.value_wei),
            data_hash=_calldata_hash(tx.data),
            meta=tx.meta or {},
            status='PENDING',
        )

    # If we never configured a middleware URL, short-circuit to simulation.
    if not _middleware_url() or not _shared_secret():
        if _allow_simulate():
            audit.tx_hash = _simulated_hash(client_tx_id)
            audit.status = 'SIMULATED'
            audit.last_error = 'middleware_not_configured'
            audit.save(update_fields=['tx_hash', 'status', 'last_error', 'updated_at'])
            return SubmitResult(audit.tx_hash, audit.chain_id, 'SIMULATED',
                                client_tx_id, simulated=True, error='middleware_not_configured')
        audit.status = 'FAILED'
        audit.last_error = 'middleware_not_configured'
        audit.save(update_fields=['status', 'last_error', 'updated_at'])
        return SubmitResult('', audit.chain_id, 'FAILED', client_tx_id,
                            error='middleware_not_configured')

    body = {
        'mode': 'system',
        'clientTxId': client_tx_id,
        'to': tx.to_address,
        'data': tx.data,
        'value': str(tx.value_wei),
        'module': tx.module,
        'action': tx.action,
        'meta': tx.meta or {},
    }
    return _submit_with_retries(audit, body)


def raw_submit(tx: RawTx) -> SubmitResult:
    """
    User-signed transaction from a mobile/desktop device. The Django
    backend acts purely as a relay: it writes the audit row and forwards
    the already-signed blob. The signer is the user; we never see their key.
    """
    client_tx_id = _new_client_tx_id(tx.module, tx.action)

    with db_transaction.atomic():
        audit = TxAuditLog.objects.create(
            client_tx_id=client_tx_id,
            module=tx.module,
            action=tx.action,
            mode='raw',
            actor_id=tx.actor_id,
            chain_id=_chain_id(),
            to_address=tx.to_address,
            value_wei=str(tx.value_wei),
            data_hash='',  # opaque to us — it's inside the signed blob
            meta=tx.meta or {},
            status='PENDING',
        )

    if not _middleware_url() or not _shared_secret():
        audit.status = 'FAILED'
        audit.last_error = 'middleware_not_configured'
        audit.save(update_fields=['status', 'last_error', 'updated_at'])
        return SubmitResult('', audit.chain_id, 'FAILED', client_tx_id,
                            error='middleware_not_configured')

    body = {
        'mode': 'raw',
        'clientTxId': client_tx_id,
        'signedTx': tx.signed_tx,
        'module': tx.module,
        'action': tx.action,
        'meta': tx.meta or {},
    }
    return _submit_with_retries(audit, body)
