"""
Firebase Auth middleware for Django.

Verifies the `Authorization: Bearer <id_token>` header against Firebase Auth,
resolves the Firebase UID, and attaches it to request.firebase_uid. Does NOT
replace Django's session auth; sits alongside it so API endpoints can adopt
Firebase Auth gradually.

Usage: add to MIDDLEWARE in settings.py after AuthenticationMiddleware:

    MIDDLEWARE = [
        ...,
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'firebase_integration.auth_middleware.FirebaseAuthMiddleware',
        ...
    ]
"""
import logging

from django.utils.deprecation import MiddlewareMixin

from .admin_init import get_auth

logger = logging.getLogger(__name__)


class FirebaseAuthMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request.firebase_uid = None
        request.firebase_claims = None

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[len('Bearer '):].strip()
        if not token:
            return None

        try:
            decoded = get_auth().verify_id_token(token, check_revoked=False)
            request.firebase_uid = decoded.get('uid')
            request.firebase_claims = decoded
        except Exception as e:
            logger.debug('Firebase token verification failed: %s', e)
            return None

        return None
