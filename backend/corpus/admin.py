from django.contrib import admin
from .models import CorpusFund, Deposit, Investment, Settlement


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
