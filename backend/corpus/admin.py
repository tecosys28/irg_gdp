from django.contrib import admin
from django.contrib import messages
from .models import CorpusFund, Deposit, Investment, Settlement, CorpusBankAccount


@admin.register(CorpusFund)
class CorpusFundAdmin(admin.ModelAdmin):
    list_display  = ['jeweler', 'total_balance', 'gold_grams_held', 'physical_gold_value', 'updated_at']
    search_fields = ['jeweler__business_name', 'blockchain_address']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display  = ['depositor', 'corpus_fund', 'amount', 'deposit_type', 'status', 'deposited_at']
    list_filter   = ['deposit_type', 'status']
    search_fields = ['depositor__email', 'reference_id', 'deposit_tx_hash']
    readonly_fields = ['id', 'deposited_at', 'confirmed_at']
    ordering      = ['-deposited_at']


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display  = ['corpus_fund', 'investment_type', 'amount', 'current_value', 'status', 'invested_at']
    list_filter   = ['investment_type', 'status']
    readonly_fields = ['id', 'invested_at']


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display  = ['corpus_fund', 'beneficiary', 'settlement_type', 'amount', 'settled_at']
    list_filter   = ['settlement_type']
    search_fields = ['beneficiary__email', 'reference_id', 'settlement_tx_hash']
    readonly_fields = ['id', 'settled_at']
    ordering      = ['-settled_at']


@admin.register(CorpusBankAccount)
class CorpusBankAccountAdmin(admin.ModelAdmin):
    list_display  = ['bank_name', 'account_number', 'ifsc_code', 'branch', 'is_active', 'updated_at', 'updated_by']
    list_filter   = ['is_active']
    readonly_fields = ['updated_at', 'updated_by']
    fieldsets = (
        ('Account Details', {
            'fields': ('account_name', 'account_number', 'account_type'),
        }),
        ('Bank Details', {
            'fields': ('bank_name', 'branch', 'city', 'postal_code', 'country', 'swift_code', 'ifsc_code'),
        }),
        ('Status', {
            'fields': ('is_active', 'updated_at', 'updated_by'),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Deactivate all other records when this one is set to active
        if obj.is_active:
            CorpusBankAccount.objects.exclude(pk=obj.pk).update(is_active=False)
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        messages.success(
            request,
            f'Bank account "{obj.bank_name} — {obj.account_number}" saved and set as active.'
            if obj.is_active else
            f'Bank account "{obj.bank_name} — {obj.account_number}" saved (inactive).'
        )
