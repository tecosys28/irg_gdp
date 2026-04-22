from django.contrib import admin
from .models import Dispute, Resolution, Compensation, AuditLog


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display  = ['case_number', 'filed_by', 'category', 'status', 'priority',
                     'amount_in_dispute', 'assigned_ombudsman', 'filed_at']
    list_filter   = ['category', 'status', 'priority']
    search_fields = ['case_number', 'filed_by__email', 'against__email', 'subject']
    readonly_fields = ['id', 'filed_at', 'resolved_at']
    ordering      = ['-filed_at']


@admin.register(Resolution)
class ResolutionAdmin(admin.ModelAdmin):
    list_display  = ['dispute', 'ombudsman', 'outcome', 'compensation_amount', 'resolved_at']
    list_filter   = ['outcome']
    search_fields = ['dispute__case_number', 'resolution_tx_hash']
    readonly_fields = ['id', 'resolved_at']


@admin.register(Compensation)
class CompensationAdmin(admin.ModelAdmin):
    list_display  = ['resolution', 'from_party', 'to_party', 'amount', 'status', 'ordered_at']
    list_filter   = ['status']
    search_fields = ['from_party__email', 'to_party__email', 'payment_tx_hash']
    readonly_fields = ['id', 'ordered_at', 'paid_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ['timestamp', 'user', 'action', 'model_name', 'object_id', 'ip_address']
    list_filter   = ['action', 'model_name']
    search_fields = ['user__email', 'model_name', 'object_id', 'ip_address']
    readonly_fields = ['id', 'timestamp']
    ordering      = ['-timestamp']
