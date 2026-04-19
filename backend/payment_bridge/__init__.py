"""
IRG PAA Bridge — Django App
Wires payment_bridge.models, paa_service and the PAABridge SDK into the
GDP Django backend so every corpus/payment operation in GDP goes through
the same canonical API that gov_v3 exposes.
"""
default_app_config = "payment_bridge.apps.PaymentBridgeConfig"

# Cached bridge singleton — avoids re-constructing per-request.
_bridge = None


def get_bridge(**overrides):
    """
    Return a process-wide configured PAABridge instance.

    Configuration is read (in precedence order):
      1. **overrides passed to this function
      2. settings.PAA_BRIDGE  (dict in settings.py)
      3. environment variables  PAA_BRIDGE_TRANSPORT, PAA_BRIDGE_ENDPOINT,
         PAA_BRIDGE_API_KEY
      4. built-in default: transport="django_local", source_system="gdp"
    """
    global _bridge
    if _bridge is not None and not overrides:
        return _bridge

    import os
    try:
        from django.conf import settings as _settings
        cfg = dict(getattr(_settings, "PAA_BRIDGE", {}) or {})
    except Exception:
        cfg = {}

    cfg.setdefault("transport", os.environ.get("PAA_BRIDGE_TRANSPORT", "django_local"))
    cfg.setdefault("endpoint", os.environ.get("PAA_BRIDGE_ENDPOINT"))
    cfg.setdefault("api_key",  os.environ.get("PAA_BRIDGE_API_KEY"))
    cfg.setdefault("source_system", "gdp")
    cfg.setdefault("actor", "gdp.system")
    cfg.update(overrides)

    from .bridge import PAABridge
    b = PAABridge(**{k: v for k, v in cfg.items() if v is not None})
    if not overrides:
        _bridge = b
    return b


__all__ = ["get_bridge"]
