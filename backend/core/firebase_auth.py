"""
Firebase ID token authentication for Django REST Framework.

Two paths:
  1. Trusted proxy headers (X-Verified-Firebase-UID / X-Verified-Firebase-Email)
     set by the Cloud Function apiProxy after it verifies the token.
     EC2 trusts these unconditionally — they come from an internal hop.
  2. Direct Bearer token verification via Firebase Admin SDK
     (fallback for local dev / direct EC2 access).

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_firebase_app():
    import firebase_admin
    try:
        return firebase_admin.get_app()
    except ValueError:
        return None


def _get_or_create_user(uid: str, email: str):
    # Try by firebase_uid first
    try:
        user = User.objects.get(firebase_uid=uid)
        if email and user.email != email:
            user.email = email
            user.save(update_fields=['email'])
        return user, False
    except User.DoesNotExist:
        pass

    # Fall back to email lookup — handles users created before firebase_uid was set
    if email:
        try:
            user = User.objects.get(email=email)
            user.firebase_uid = uid
            update_fields = ['firebase_uid']
            if not user.username:
                user.username = email
                update_fields.append('username')
            user.save(update_fields=update_fields)
            return user, False
        except User.DoesNotExist:
            pass

    # Create fresh user
    user = User.objects.create(
        firebase_uid=uid,
        email=email or '',
        username=email or uid,
        is_active=True,
    )
    return user, True


class FirebaseAuthentication(BaseAuthentication):
    """
    Authenticates via Firebase. Accepts:
      • X-Verified-Firebase-UID header (set by Cloud Function proxy, already verified)
      • Authorization: Bearer <firebase-id-token> (verified directly here)
    """

    def authenticate(self, request):
        # ── Path 1: trusted headers from Cloud Function proxy ──────────────────
        uid = request.META.get('HTTP_X_VERIFIED_FIREBASE_UID', '').strip()
        if uid:
            email = request.META.get('HTTP_X_VERIFIED_FIREBASE_EMAIL', '').strip()
            user, _ = _get_or_create_user(uid, email)
            return (user, {'uid': uid, 'email': email, 'source': 'proxy'})

        # ── Path 2: direct Bearer token (local dev / direct EC2 access) ────────
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        id_token = auth_header[len('Bearer '):]
        if not id_token:
            return None

        app = _get_firebase_app()
        if app is None:
            raise AuthenticationFailed(
                'Firebase Admin SDK not initialised. '
                'Set FIREBASE_CREDENTIALS_JSON in the environment, '
                'or route requests through the Cloud Function proxy.'
            )

        try:
            import firebase_admin.auth as fb_auth
            decoded = fb_auth.verify_id_token(id_token, app=app, check_revoked=True)
        except Exception as exc:
            raise AuthenticationFailed(f'Invalid Firebase token: {exc}')

        uid   = decoded.get('uid')
        email = decoded.get('email', '')
        user, _ = _get_or_create_user(uid, email)
        return (user, decoded)

    def authenticate_header(self, request):
        return 'Bearer realm="irggdp"'
