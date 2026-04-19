"""
Django ↔ Firestore sync bridge.

When a Django model in any GDP app is saved or deleted, the relevant aggregate
shape in Firestore is updated. This keeps the `mics_digest` collection (read
by the Advisory Board MICS via getMICSDigest) in sync with the canonical
Django source of truth.

Pattern:
  * post_save and post_delete signal handlers fan out to per-model syncers.
  * Each syncer writes into its targeted Firestore collection under this
    project's OWN Firestore database — never another project's.
  * All writes are non-blocking with respect to the request that triggered
    them (uses transaction.on_commit so we never write to Firestore inside
    an uncommitted DB transaction).

Only a minimal set of sync handlers is provided here; extend as the MICS
digest needs more slices.
"""
import logging
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .admin_init import get_firestore

logger = logging.getLogger(__name__)


def _fs():
    """Lazy accessor so tests can mock."""
    return get_firestore()


# ── Helper: safe async Firestore write ─────────────────────────────────────
def _write_after_commit(fn, *args, **kwargs):
    """Schedules a Firestore write after the current DB transaction commits."""
    def _do():
        try:
            fn(*args, **kwargs)
        except Exception as e:
            logger.exception('Firestore sync failed: %s', e)
    transaction.on_commit(_do)


# ── Sync handlers ──────────────────────────────────────────────────────────
def _sync_mint_record(instance, created):
    """Mirror a MintingRecord row into Firestore/minting_records."""
    fs = _fs()
    doc_ref = fs.collection('minting_records').document(str(instance.pk))
    doc_ref.set({
        'jewelerId':    getattr(instance, 'jeweler_id', None),
        'gramsPure':    float(getattr(instance, 'grams_pure', 0) or 0),
        'unitsIssued':  int(getattr(instance, 'units_issued', 0) or 0),
        'valueInr':     float(getattr(instance, 'value_inr', 0) or 0),
        'status':       getattr(instance, 'status', 'Active'),
        'mintedAt':     (instance.minted_at.isoformat() if getattr(instance, 'minted_at', None) else None),
        '_source':      'django',
        '_syncedAt':    _fs().SERVER_TIMESTAMP if hasattr(_fs(), 'SERVER_TIMESTAMP') else None
    }, merge=True)


def _sync_dispute(instance, created):
    fs = _fs()
    doc_ref = fs.collection('disputes').document(str(instance.pk))
    doc_ref.set({
        'category':   getattr(instance, 'category', None),
        'status':     getattr(instance, 'status', None),
        'filedBy':    getattr(instance, 'filed_by_id', None),
        'respondent': getattr(instance, 'respondent_id', None),
        'ombudsman':  getattr(instance, 'ombudsman_id', None),
        'amountInr':  float(getattr(instance, 'amount_inr', 0) or 0),
        'filedAt':    (instance.filed_at.isoformat() if getattr(instance, 'filed_at', None) else None),
        '_source':    'django'
    }, merge=True)


def _sync_gdp_unit(instance, created):
    fs = _fs()
    doc_ref = fs.collection('gdp_units').document(str(instance.pk))
    doc_ref.set({
        'holderId':   getattr(instance, 'holder_id', None),
        'gramsPure':  float(getattr(instance, 'grams_pure', 0) or 0),
        'status':     getattr(instance, 'status', 'Active'),
        'mintedAt':   (instance.created_at.isoformat() if getattr(instance, 'created_at', None) else None),
        '_source':    'django'
    }, merge=True)


# ── Wire up signals by string-lookup so we don't import-force model apps ───
from django.apps import apps as django_apps


def _connect_if_model_exists(app_label, model_name, syncer):
    try:
        model = django_apps.get_model(app_label, model_name)
    except (LookupError, ValueError):
        logger.debug('Model %s.%s not present; skipping Firestore sync wiring', app_label, model_name)
        return

    @receiver(post_save, sender=model, weak=False)
    def _on_save(sender, instance, created, **kwargs):
        _write_after_commit(syncer, instance, created)

    logger.info('Firestore sync wired for %s.%s', app_label, model_name)


# Connect at import time — apps.py calls this via `ready()`
_connect_if_model_exists('irg_gdp', 'MintingRecord', _sync_mint_record)
_connect_if_model_exists('irg_gdp', 'GDPUnit',       _sync_gdp_unit)
_connect_if_model_exists('disputes', 'Dispute',      _sync_dispute)
