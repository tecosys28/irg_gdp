"""
IRG Chain 888101 — Transaction guard.

Single enforcement point that every view which would cause a blockchain
transaction must consult BEFORE it calls BlockchainService. Usage:

    from wallet_access.guard import require_transactable

    @require_transactable(require_nominees=True)
    def mint_view(request):
        ...

Or, for explicit programmatic checks:

    from wallet_access.guard import wallet_check

    check = wallet_check(request.user, require_nominees=True)
    if not check.allowed:
        return Response({'error': check.reason}, status=403)

The guard:

  1. Loads the user's WalletActivation row (creates-on-first-access if missing)
  2. Refuses if state is not ACTIVATED
  3. Refuses if the wallet is LOCKED / SUSPENDED / RECOVERING / RECOVERED
  4. When require_nominees=True: refuses if the wallet has fewer than two
     active nominees, OR if nominee shares don't sum to 100
  5. When require_active_device=True: refuses if the user has no ACTIVE
     (past cooling-off) device

Each failure returns a stable error code so the frontend can render the
right activation banner and call-to-action.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import wraps
from typing import Optional

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .models import NomineeRegistration, WalletActivation, WalletDevice


@dataclass
class GuardResult:
    allowed: bool
    code: str = ''
    reason: str = ''
    wallet: Optional[WalletActivation] = None


def wallet_check(user, *, require_nominees: bool = False,
                 require_active_device: bool = True) -> GuardResult:
    if not user or not user.is_authenticated:
        return GuardResult(False, 'not_authenticated', 'Sign in required')

    wallet = getattr(user, 'wallet_activation', None)
    if wallet is None:
        return GuardResult(False, 'wallet_missing',
                           'No wallet found for this account. Please complete registration.')

    if not wallet.is_transactable:
        return GuardResult(
            False,
            f'wallet_{wallet.state.lower()}',
            wallet.blocking_reason,
            wallet=wallet,
        )

    if require_nominees:
        active = wallet.nominees.filter(active=True)
        if active.count() < 2:
            return GuardResult(
                False,
                'nominees_required',
                'At least two nominees must be registered before you can transact.',
                wallet=wallet,
            )
        total = sum((n.share_percent for n in active), Decimal('0'))
        if total != Decimal('100'):
            return GuardResult(
                False,
                'nominee_shares_invalid',
                f'Nominee shares must total 100% (currently {total}%).',
                wallet=wallet,
            )

    if require_active_device:
        now = timezone.now()
        # A device is "transaction-ready" when it is ACTIVE and its
        # cooling-off period has expired (or was never set).
        ready_devices = [
            d for d in wallet.devices.filter(state='ACTIVE')
            if d.cooling_off_until is None or d.cooling_off_until <= now
        ]
        if not ready_devices:
            return GuardResult(
                False,
                'device_not_ready',
                'No device is currently authorised to sign transactions for this wallet.',
                wallet=wallet,
            )

    return GuardResult(True, 'ok', '', wallet=wallet)


# ─────────────────────────────────────────────────────────────────────────────
# DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def require_transactable(require_nominees: bool = False,
                         require_active_device: bool = True):
    """
    DRF view decorator. Blocks the request with HTTP 403 and a structured
    error body if the caller's wallet cannot currently transact.

    Works on both:
      * function-based views: def my_view(request, ...)
      * DRF viewset action methods: def my_action(self, request, ...)

    Detection is based on whether the first positional arg is a Request
    instance or something else (the viewset `self`).
    """
    from rest_framework.request import Request

    def deco(view_func):
        @wraps(view_func)
        def _wrapped(*args, **kwargs):
            # Locate the DRF Request object. For function views it's args[0];
            # for viewset actions it's args[1] (args[0] is `self`).
            request = None
            for a in args[:2]:
                if isinstance(a, Request):
                    request = a
                    break
            if request is None:
                # Last resort — fall back to the first arg (may be a plain
                # HttpRequest in non-DRF contexts).
                request = args[0] if args else None

            user = getattr(request, 'user', None)
            result = wallet_check(
                user,
                require_nominees=require_nominees,
                require_active_device=require_active_device,
            )
            if not result.allowed:
                return Response(
                    {
                        'error': result.reason,
                        'code': result.code,
                        'wallet_state': result.wallet.state if result.wallet else None,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(*args, **kwargs)

        return _wrapped

    return deco
