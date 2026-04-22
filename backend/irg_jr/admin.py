from django.contrib import admin
from .models import JRUnit, IssuanceRecord, BuybackRecord, RedemptionRecord, GoldAssessment


@admin.register(JRUnit)
class JRUnitAdmin(admin.ModelAdmin):
    list_display  = ['blockchain_id', 'owner', 'issuing_jeweler', 'jewelry_type',
                     'gold_weight', 'purity', 'issue_value', 'status', 'issued_at']
    list_filter   = ['jewelry_type', 'purity', 'status']
    search_fields = ['blockchain_id', 'owner__email', 'issuing_jeweler__business_name']
    readonly_fields = ['id', 'issued_at', 'blockchain_id', 'issuance_tx_hash']
    ordering      = ['-issued_at']


@admin.register(IssuanceRecord)
class IssuanceRecordAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'jeweler', 'invoice_number', 'corpus_contribution',
                     'status', 'created_at']
    list_filter   = ['status']
    search_fields = ['customer__email', 'jeweler__business_name', 'invoice_number', 'utr_number']
    readonly_fields = ['id', 'created_at']
    ordering      = ['-created_at']


@admin.register(BuybackRecord)
class BuybackRecordAdmin(admin.ModelAdmin):
    list_display  = ['jr_unit', 'requested_by', 'buyback_value', 'benchmark_at_buyback',
                     'status', 'requested_at']
    list_filter   = ['status']
    search_fields = ['requested_by__email', 'buyback_tx_hash']
    readonly_fields = ['id', 'requested_at', 'completed_at']
    ordering      = ['-requested_at']


@admin.register(RedemptionRecord)
class RedemptionRecordAdmin(admin.ModelAdmin):
    list_display  = ['jr_unit', 'redeemed_by', 'redeemed_at', 'delivered_at']
    search_fields = ['redeemed_by__email', 'redemption_tx_hash']
    readonly_fields = ['id', 'redeemed_at']
    ordering      = ['-redeemed_at']


@admin.register(GoldAssessment)
class GoldAssessmentAdmin(admin.ModelAdmin):
    list_display  = ['certificate_number', 'jeweler', 'customer_email', 'purity',
                     'test_method', 'estimated_value', 'status', 'created_at']
    list_filter   = ['purity', 'test_method', 'status']
    search_fields = ['certificate_number', 'customer_email', 'jeweler__business_name']
    readonly_fields = ['id', 'created_at']
    ordering      = ['-created_at']
