"""
Activity tracker — touches wallet.last_activity_at on every authenticated
request so the inactivity watchdog only fires for genuinely quiet wallets.

Lightweight. The DB write is limited to once per hour per user via an
in-process cache to avoid a write on every single page load.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import time
from threading import RLock


_last_touch: dict[int, float] = {}
_lock = RLock()
_TOUCH_INTERVAL_SECONDS = 3600   # touch DB at most once per hour per user


def _should_touch(user_id: int) -> bool:
    now = time.time()
    with _lock:
        last = _last_touch.get(user_id, 0.0)
        if now - last < _TOUCH_INTERVAL_SECONDS:
            return False
        _last_touch[user_id] = now
        return True


class WalletActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            user = getattr(request, 'user', None)
            if user and getattr(user, 'is_authenticated', False) and _should_touch(user.id):
                # Lazy import avoids a circular import at module load time.
                from .services import touch_activity
                touch_activity(user)
        except Exception:
            # Activity tracking is best-effort; never break a response.
            pass
        return response
