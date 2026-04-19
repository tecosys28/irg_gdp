"""
Firebase Admin SDK bootstrap for irg_gdp.

Reads credentials from either:
  * env var GOOGLE_APPLICATION_CREDENTIALS pointing to a service-account JSON
  * env var FIREBASE_CREDENTIALS_JSON containing the raw JSON string
  * Application Default Credentials if running on Google Cloud (Cloud Run)

Project ID is always read from FIREBASE_PROJECT_ID env var so the same image
can target prod or staging by env alone.
"""
import json
import logging
import os

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

_initialized = False


def get_app():
    """Returns the Firebase app instance, initialising on first call."""
    global _initialized
    if _initialized:
        return firebase_admin.get_app()

    project_id = os.environ.get('FIREBASE_PROJECT_ID', 'irg-gdp-prod')

    # Precedence: explicit JSON env > file path env > ADC
    cred = None
    raw_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

    if raw_json:
        try:
            cred = credentials.Certificate(json.loads(raw_json))
        except Exception as e:
            logger.error('FIREBASE_CREDENTIALS_JSON invalid: %s', e)
    elif cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # Let firebase_admin fall back to ADC (works on Cloud Run)
        cred = credentials.ApplicationDefault()

    try:
        app = firebase_admin.initialize_app(cred, {'projectId': project_id})
        _initialized = True
        logger.info('Firebase Admin initialised for project %s', project_id)
        return app
    except ValueError:
        # Already initialised elsewhere
        _initialized = True
        return firebase_admin.get_app()


def get_firestore():
    """Returns a Firestore client. Initialises the app if needed."""
    from firebase_admin import firestore
    get_app()
    return firestore.client()


def get_auth():
    """Returns the Firebase Auth admin helper. Initialises the app if needed."""
    from firebase_admin import auth
    get_app()
    return auth
