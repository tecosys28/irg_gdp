<<<<<<< HEAD
import json
import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # noqa
        self._init_firebase()

    def _init_firebase(self):
        try:
            import firebase_admin
            from firebase_admin import credentials

            try:
                firebase_admin.get_app()
                return
            except ValueError:
                pass

            creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON', '')
            creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')

            if creds_json:
                cred = credentials.Certificate(json.loads(creds_json))
            elif creds_path and os.path.isfile(creds_path):
                cred = credentials.Certificate(creds_path)
            else:
                cred = credentials.ApplicationDefault()

            project_id = os.environ.get('FIREBASE_PROJECT_ID', 'irggdp')
            firebase_admin.initialize_app(cred, {'projectId': project_id})
            logger.info('[firebase] Admin SDK initialised for project %s', project_id)
        except Exception as exc:
            logger.error('[firebase] Failed to initialise Admin SDK: %s', exc)
=======
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        import core.signals  # noqa
>>>>>>> 6f5e39f (changhes05)
