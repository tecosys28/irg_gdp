"""
firebase_integration — Django app that wires the IRG_GDP backend to its
own Firebase project (irg-gdp-prod).

On AppConfig.ready():
  * initialises firebase_admin with the service-account JSON pointed to by
    GOOGLE_APPLICATION_CREDENTIALS (or FIREBASE_CREDENTIALS_JSON in-line).
  * connects Django post_save signals to sync handlers in firestore_sync.py

The Firebase project belongs exclusively to this app. It is NOT shared with
irg_gov, irg_ftr, irg_chain or dac_platform.
"""
from django.apps import AppConfig


class FirebaseIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'firebase_integration'
    verbose_name = 'Firebase Integration (irg-gdp-prod)'

    def ready(self):
        from . import admin_init  # initialises firebase_admin at import time
        from . import firestore_sync  # wires signal handlers (import has side effects)
        _ = admin_init, firestore_sync  # silence linters
