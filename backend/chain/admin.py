from django.contrib import admin
from django.contrib import messages
from .models import TxAuditLog, ChainWatcherCursor, EscrowReconciliationLog


# ── TxAuditLog actions ────────────────────────────────────────────────────────

def _retry_failed_tx(modeladmin, request, queryset):
    from chain.client import system_submit, SystemTx
    retried = 0
    for log in queryset.filter(status='FAILED'):
        try:
            result = system_submit(SystemTx(
                module=log.module,
                action=log.action,
                to_address=log.to_address or '',
                data='0x',
                meta={**log.meta, 'admin_retry': True, 'original_client_tx_id': log.client_tx_id},
                actor_id=log.actor_id,
            ))
            if result.status in ('SUBMITTED', 'SIMULATED'):
                retried += 1
        except Exception as e:
            modeladmin.message_user(request, f'Retry failed for {log.client_tx_id}: {e}', messages.ERROR)

    if retried:
        modeladmin.message_user(request, f'{retried} transaction(s) retried successfully.', messages.SUCCESS)

def _mark_tx_simulated(modeladmin, request, queryset):
    updated = queryset.filter(status='FAILED').update(status='SIMULATED')
    modeladmin.message_user(
        request,
        f'{updated} transaction(s) marked SIMULATED (use only in dev/staging).',
        messages.WARNING,
    )

_retry_failed_tx.short_description    = 'Retry selected FAILED transactions'
_mark_tx_simulated.short_description  = 'Mark selected FAILED transactions as SIMULATED (dev only)'


# ── Admin classes ─────────────────────────────────────────────────────────────

@admin.register(TxAuditLog)
class TxAuditLogAdmin(admin.ModelAdmin):
    list_display    = ['client_tx_id', 'module', 'action', 'mode', 'status', 'actor', 'created_at']
    list_filter     = ['status', 'module', 'mode']
    search_fields   = ['client_tx_id', 'tx_hash', 'actor__email', 'module', 'action']
    readonly_fields = ['client_tx_id', 'created_at', 'updated_at', 'confirmed_at',
                       'tx_hash', 'data_hash', 'chain_id']
    ordering        = ['-created_at']
    actions         = [_retry_failed_tx, _mark_tx_simulated]


@admin.register(ChainWatcherCursor)
class ChainWatcherCursorAdmin(admin.ModelAdmin):
    list_display    = ['name', 'last_block', 'updated_at']
    readonly_fields = ['updated_at']


@admin.register(EscrowReconciliationLog)
class EscrowReconciliationLogAdmin(admin.ModelAdmin):
    list_display    = ['run_date', 'status', 'escrow_locked_count', 'escrow_released_count',
                       'discrepancy_inr', 'created_at']
    list_filter     = ['status']
    readonly_fields = ['created_at']
    ordering        = ['-run_date']
