from django.contrib import admin
from .models import TxAuditLog, ChainWatcherCursor, EscrowReconciliationLog


@admin.register(TxAuditLog)
class TxAuditLogAdmin(admin.ModelAdmin):
    list_display  = ['client_tx_id', 'module', 'action', 'mode', 'status', 'actor', 'created_at']
    list_filter   = ['status', 'module', 'mode']
    search_fields = ['client_tx_id', 'tx_hash', 'actor__email', 'module', 'action']
    readonly_fields = ['client_tx_id', 'created_at', 'updated_at', 'confirmed_at']
    ordering      = ['-created_at']


@admin.register(ChainWatcherCursor)
class ChainWatcherCursorAdmin(admin.ModelAdmin):
    list_display  = ['name', 'last_block', 'updated_at']
    readonly_fields = ['updated_at']


@admin.register(EscrowReconciliationLog)
class EscrowReconciliationLogAdmin(admin.ModelAdmin):
    list_display  = ['run_date', 'status', 'escrow_locked_count', 'escrow_released_count',
                     'discrepancy_inr', 'created_at']
    list_filter   = ['status']
    readonly_fields = ['created_at']
    ordering      = ['-run_date']
