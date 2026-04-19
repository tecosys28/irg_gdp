"""
Licence enforcement middleware.

Blocks every request if the licence is invalid. Reads only the cached
flag — no crypto or disk I/O on the hot path.

IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
"""

from django.http import JsonResponse

from .licence_guard import STATE


EXEMPT_PATHS = {
    "/healthz",
    "/licence/status",
    "/chain/licence/status",
}


class LicenceEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in EXEMPT_PATHS:
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
