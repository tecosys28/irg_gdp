from django.contrib import admin
from .models import (PaaCorpusFund, PaaTransaction, PaaBudget,
                     PaaTrustee, PaaCourtApproval, PaaAuditLog, PaaRuleChange)


@admin.register(PaaCorpusFund)
class PaaCorpusFundAdmin(admin.ModelAdmin):
    list_display  = ['name', 'cf_type', 'country_code', 'primary_currency',
                     'min_required_balance', 'is_active', 'last_updated']
    list_filter   = ['cf_type', 'is_active', 'country_code']
    search_fields = ['name', 'owner_id', 'bank_name', 'trustee_banker_name']
    readonly_fields = ['id', 'created_at', 'last_updated']


@admin.register(PaaTransaction)
class PaaTransactionAdmin(admin.ModelAdmin):
    list_display  = ['id', 'tx_type', 'category', 'amount', 'currency',
                     'from_account', 'to_cf', 'status', 'created_at']
    list_filter   = ['status', 'category', 'currency']
    search_fields = ['id', 'idempotency_key', 'from_account', 'to_cf',
                     'blockchain_tx_hash', 'source_ref']
    readonly_fields = ['id', 'created_at', 'executed_at', 'cancelled_at']
    ordering      = ['-created_at']


@admin.register(PaaBudget)
class PaaBudgetAdmin(admin.ModelAdmin):
    list_display  = ['budget_id', 'version', 'total_corpus_limit', 'total_corpus_currency',
                     'is_active', 'effective_from', 'updated_at']
    list_filter   = ['is_active', 'total_corpus_currency']
    search_fields = ['budget_id', 'updated_by']
    readonly_fields = ['updated_at']


@admin.register(PaaTrustee)
class PaaTrusteeAdmin(admin.ModelAdmin):
    list_display  = ['name', 'license_ref', 'country', 'status', 'last_updated']
    list_filter   = ['status', 'country']
    search_fields = ['name', 'license_ref']
    readonly_fields = ['id', 'registered_at', 'last_updated']


@admin.register(PaaCourtApproval)
class PaaCourtApprovalAdmin(admin.ModelAdmin):
    list_display  = ['id', 'file_name', 'uploaded_by', 'related_tx_id', 'uploaded_at']
    search_fields = ['id', 'uploaded_by', 'document_hash', 'related_tx_id']
    readonly_fields = ['id', 'uploaded_at']


@admin.register(PaaAuditLog)
class PaaAuditLogAdmin(admin.ModelAdmin):
    list_display  = ['timestamp', 'action', 'actor']
    list_filter   = ['action']
    search_fields = ['action', 'actor']
    readonly_fields = ['id', 'timestamp']
    ordering      = ['-timestamp']


@admin.register(PaaRuleChange)
class PaaRuleChangeAdmin(admin.ModelAdmin):
    list_display  = ['title', 'change_type', 'proposed_by', 'status',
                     'required_votes', 'proposed_at']
    list_filter   = ['change_type', 'status']
    search_fields = ['title', 'proposed_by', 'court_approval_id']
    readonly_fields = ['id', 'proposed_at', 'implemented_at']
    ordering      = ['-proposed_at']
