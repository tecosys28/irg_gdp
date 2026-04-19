"""
Chain app config — also the startup hook for the licence guard.

IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
"""

import os
import sys

from django.apps import AppConfig


class ChainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chain'
    verbose_name = 'IRG Chain 888101 Integration'

    def ready(self) -> None:
        if os.environ.get("IRG_LICENCE_SKIP_STARTUP") == "1":
            return
        skip_cmds = {"makemigrations", "migrate", "collectstatic",
                     "check", "shell", "createsuperuser", "test"}
        if any(cmd in sys.argv for cmd in skip_cmds):
            return

        try:
            from .licence_guard import verify_licence_or_die
            verify_licence_or_die(product_code="GDP")
        except ImportError:
            import logging
            logging.getLogger("irg.licence").warning(
                "licence_guard unavailable; running without verification"
            )
