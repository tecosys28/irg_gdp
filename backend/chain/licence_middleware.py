"""
Licence enforcement middleware.

Blocks every request if the licence is invalid. Reads only the cached
flag — no crypto or disk I/O on the hot path.

IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
"""

import os

from django.http import JsonResponse

from .licence_guard import STATE

EXEMPT_PATHS = {
    "/healthz",
    "/licence/status",
    "/chain/licence/status",
}

# Bypass when:
#   1. DEBUG mode (local dev / CI)
#   2. No licence token path configured (token file doesn't exist) — allows
#      deployments that don't yet have a signed licence to still serve the API
#   3. Explicit env var override (e.g. staging without a licence token)
_DEBUG = os.environ.get("DJANGO_DEBUG", os.environ.get("DEBUG", "False")) == "True"
_TOKEN_PATH = os.environ.get("IRG_LICENCE_TOKEN_PATH", "/etc/irg/licence.token")
_BYPASS = _DEBUG or not os.path.isfile(_TOKEN_PATH) or \
          os.environ.get("IRG_LICENCE_BYPASS", "False") == "True"


class LicenceEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _BYPASS or request.path in EXEMPT_PATHS:
            return self.get_response(request)
        if not STATE.valid:
            return JsonResponse(
                {
                    "error": "licence_invalid",
                    "reason": STATE.reason,
                    "message": (
                        "This deployment is not currently licensed. "
                        "Contact the licensor."
                    ),
                },
                status=503,
            )
        return self.get_response(request)
