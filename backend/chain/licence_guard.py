"""
IRG Licence Guard — Django / Python runtime validator.

Perpetual licence, Ed25519-signed. Verification checks:
  1. Signature matches the embedded public key
  2. Deployment fingerprint matches what was signed
  3. Product is listed in permitted products
  4. Issuance timestamp is not in the future

Usage in Django:
  # In your AppConfig.ready():
  from .licence_guard import verify_licence_or_die
  verify_licence_or_die(product_code='GDP')

IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
"""

import base64
import hashlib
import json
import logging
import os
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("irg.licence")

# Hard-coded public key — replaced at build time by bootstrap.sh.
LICENCE_PUBLIC_KEY_HEX = os.environ.get(
    "IRG_LICENCE_PUBLIC_KEY_HEX",
    "0000000000000000000000000000000000000000000000000000000000000000",
)

LICENCE_TOKEN_PATH = os.environ.get("IRG_LICENCE_TOKEN_PATH", "/etc/irg/licence.token")
LICENCE_FINGERPRINT_SALT = b"irg-fingerprint-v1"
RECHECK_INTERVAL_SECONDS = 60 * 60


class LicenceError(Exception):
    pass


class _State:
    valid: bool = False
    reason: str = "not_checked"
    payload: Optional[dict] = None
    last_good_at: float = 0.0
    last_check_at: float = 0.0


STATE = _State()
_lock = threading.Lock()


def _primary_mac() -> str:
    try:
        return f"{uuid.getnode():012x}"
    except Exception:
        return "unknown"


def _chain_id() -> str:
    return os.environ.get("IRG_CHAIN_ID", "888101")


def _build_version() -> str:
    return os.environ.get("IRG_BUILD_VERSION", "v1.0")


def compute_deployment_fingerprint() -> str:
    h = hashlib.sha256()
    h.update(LICENCE_FINGERPRINT_SALT)
    h.update(_primary_mac().encode())
    h.update(b"|")
    h.update(socket.gethostname().encode())
    h.update(b"|")
    h.update(_chain_id().encode())
    h.update(b"|")
    h.update(_build_version().encode())
    return h.hexdigest()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _verify_ed25519(message: bytes, signature: bytes, pubkey: bytes) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        logger.critical("cryptography library missing — cannot verify licence")
        return False
    try:
        pk = Ed25519PublicKey.from_public_bytes(pubkey)
        pk.verify(signature, message)
        return True
    except Exception:
        return False


def _parse_token(token: str) -> dict:
    parts = token.strip().split(".")
    if len(parts) != 2:
        raise LicenceError("malformed_token")
    payload_b = _b64url_decode(parts[0])
    sig = _b64url_decode(parts[1])
    try:
        pubkey = bytes.fromhex(LICENCE_PUBLIC_KEY_HEX)
    except ValueError:
        raise LicenceError("bad_public_key_config")
    if len(pubkey) != 32:
        raise LicenceError("bad_public_key_length")
    if not _verify_ed25519(payload_b, sig, pubkey):
        raise LicenceError("bad_signature")
    try:
        return json.loads(payload_b)
    except json.JSONDecodeError:
        raise LicenceError("bad_payload_json")


def _verify_once(product_code: str):
    path = Path(LICENCE_TOKEN_PATH)
    if not path.is_file():
        return False, f"token_not_found:{path}", None
    try:
        raw = path.read_text().strip()
        payload = _parse_token(raw)
    except (LicenceError, PermissionError) as e:
        return False, str(e), None

    if payload.get("v") != 2:
        return False, "unsupported_version", None

    now = int(time.time())
    if int(payload.get("iat", 0)) > now + 300:
        return False, "issued_in_future", payload

    if payload.get("fp", "").lower() != compute_deployment_fingerprint():
        return False, "fingerprint_mismatch", payload

    if product_code.upper() not in [p.upper() for p in payload.get("products", [])]:
        return False, "product_not_licensed", payload

    return True, "ok", payload


def verify_licence_or_die(product_code: str = "GDP") -> None:
    """Call from AppConfig.ready(). Terminates the process on invalid licence."""
    valid, reason, payload = _verify_once(product_code)
    with _lock:
        STATE.valid = valid
        STATE.reason = reason
        STATE.payload = payload
        STATE.last_check_at = time.time()
        if valid:
            STATE.last_good_at = time.time()

    if not valid:
        logger.critical(
            "[irg.licence] LICENCE INVALID (%s) — refusing to start. "
            "Contact the licensor.", reason,
        )
        if os.environ.get("IRG_LICENCE_TEST_MODE") == "1":
            raise LicenceError(reason)
        os._exit(2)

    logger.info(
        "[irg.licence] OK — %s licensed to %s (%s), serial %s",
        product_code,
        payload.get("name", "?"),
        payload.get("sub", "?"),
        payload.get("serial", "?"),
    )

    if not getattr(verify_licence_or_die, "_thread_started", False):
        verify_licence_or_die._thread_started = True
        threading.Thread(
            target=_recheck_loop, args=(product_code,),
            daemon=True, name="irg-licence-recheck",
        ).start()


def _recheck_loop(product_code: str) -> None:
    while True:
        time.sleep(RECHECK_INTERVAL_SECONDS)
        try:
            valid, reason, payload = _verify_once(product_code)
        except Exception as e:
            logger.warning("[irg.licence] recheck error: %s", e)
            continue
        with _lock:
            STATE.valid = valid
            STATE.reason = reason
            STATE.payload = payload
            STATE.last_check_at = time.time()
            if valid:
                STATE.last_good_at = time.time()
        if not valid:
            logger.error("[irg.licence] recheck failed: %s", reason)


def current_licence_info() -> dict:
    with _lock:
        return {
            "valid": STATE.valid,
            "reason": STATE.reason,
            "last_check_at": STATE.last_check_at,
            "last_good_at": STATE.last_good_at,
            "licensee": STATE.payload.get("name") if STATE.payload else None,
            "licensee_uid": STATE.payload.get("sub") if STATE.payload else None,
            "serial": STATE.payload.get("serial") if STATE.payload else None,
            "products": STATE.payload.get("products") if STATE.payload else [],
            "territory": STATE.payload.get("territory") if STATE.payload else [],
        }
