from django.apps import AppConfig


class PaymentBridgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payment_bridge"
    verbose_name = "IRG Payment Autonomy Bridge"

    def ready(self):  # noqa: D401 — simple pass-through
        # Import the service module so Django's app registry has eyes on it,
        # and seed on first run in dev mode (safe; idempotent).
        from . import paa_service  # noqa: F401
