"""
Firebase ID token authentication for Django REST Framework.

Verifies the Bearer token sent by the frontend (Firebase JS SDK),
looks up or creates the matching local User, and sets request.user.

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


class FirebaseAuthentication(BaseAuthentication):
    """
    Reads `Authorization: Bearer <firebase-id-token>` and verifies it
    against the Firebase project. On success, returns (user, token_payload).
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        id_token = auth_header[len('Bearer '):]
        if not id_token:
            return None

        app = _get_firebase_app()
        if app is None:
            raise AuthenticationFailed('Firebase not initialised on this server.')

        try:
            import firebase_admin.auth as fb_auth
            decoded = fb_auth.verify_id_token(id_token, app=app, check_revoked=True)
        except Exception as exc:
            raise AuthenticationFailed(f'Invalid Firebase token: {exc}')

        uid = decoded.get('uid')
        email = decoded.get('email', '')

        user, created = User.objects.get_or_create(
            firebase_uid=uid,
            defaults={
                'email': email,
                'username': email or uid,
                'is_active': True,
            },
        )

        if not created and email and user.email != email:
            user.email = email
            user.save(update_fields=['email'])

        return (user, decoded)

    def authenticate_header(self, request):
        return 'Bearer realm="irggdp"'
