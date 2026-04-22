from django.contrib import admin
from .models import (GDPUnit, MintingRecord, EarmarkingRecord,
                     BonusAllocation, SwapRecord, TradeRecord, TransferRecord)


@admin.register(GDPUnit)
class GDPUnitAdmin(admin.ModelAdmin):
    list_display  = ['blockchain_id', 'owner', 'gold_grams', 'purity', 'pure_gold_equivalent',
                     'total_units', 'status', 'minted_at']
    list_filter   = ['purity', 'status']
    search_fields = ['blockchain_id', 'owner__email', 'minting_tx_hash']
    readonly_fields = ['id', 'minted_at', 'updated_at']
    ordering      = ['-minted_at']


@admin.register(MintingRecord)
class MintingRecordAdmin(admin.ModelAdmin):
    list_display  = ['user', 'gold_grams', 'purity', 'units_to_mint', 'status',
                     'invoice_verified', 'jeweler_certified', 'created_at']
    list_filter   = ['status', 'purity', 'invoice_verified', 'jeweler_certified']
    search_fields = ['user__email', 'invoice_hash', 'transaction_hash']
    readonly_fields = ['id', 'created_at', 'completed_at']
    ordering      = ['-created_at']


@admin.register(EarmarkingRecord)
class EarmarkingRecordAdmin(admin.ModelAdmin):
    list_display  = ['user', 'gdp_unit', 'amount', 'rate_percent', 'status',
                     'earmarked_at', 'release_date']
    list_filter   = ['status']
    search_fields = ['user__email', 'earmark_tx_hash']
    readonly_fields = ['id', 'earmarked_at', 'released_at']
    ordering      = ['-earmarked_at']


@admin.register(BonusAllocation)
class BonusAllocationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'amount', 'source', 'period', 'status', 'allocated_at']
    list_filter   = ['source', 'status']
    search_fields = ['user__email', 'period']
    readonly_fields = ['id', 'allocated_at', 'distributed_at']
    ordering      = ['-allocated_at']


@admin.register(SwapRecord)
class SwapRecordAdmin(admin.ModelAdmin):
    list_display  = ['user', 'gdp_units_swapped', 'gdp_value_at_swap', 'ftr_category',
                     'ftr_units_received', 'status', 'initiated_at']
    list_filter   = ['ftr_category', 'status']
    search_fields = ['user__email', 'swap_tx_hash']
    readonly_fields = ['id', 'initiated_at', 'completed_at']
    ordering      = ['-initiated_at']


@admin.register(TradeRecord)
class TradeRecordAdmin(admin.ModelAdmin):
    list_display  = ['trade_type', 'user', 'counterparty', 'units', 'price_per_unit',
                     'total_value', 'status', 'created_at']
    list_filter   = ['trade_type', 'status']
    search_fields = ['user__email', 'counterparty__email', 'trade_tx_hash']
    readonly_fields = ['id', 'created_at', 'executed_at']
    ordering      = ['-created_at']


@admin.register(TransferRecord)
class TransferRecordAdmin(admin.ModelAdmin):
    list_display  = ['from_user', 'to_user', 'gdp_unit', 'transfer_type', 'transferred_at']
    list_filter   = ['transfer_type']
    search_fields = ['from_user__email', 'to_user__email', 'transfer_tx_hash']
    readonly_fields = ['id', 'transferred_at']
    ordering      = ['-transferred_at']
