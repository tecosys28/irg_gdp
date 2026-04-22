from django.contrib import admin
from .models import LBMARate, BenchmarkValue, OracleNode, PriceFeed


@admin.register(LBMARate)
class LBMARateAdmin(admin.ModelAdmin):
    list_display  = ['date', 'metal', 'am_fix_usd', 'pm_fix_usd', 'inr_per_gram',
                     'change_percent', 'source', 'recorded_at']
    list_filter   = ['metal']
    search_fields = ['metal', 'source', 'blockchain_tx_hash']
    readonly_fields = ['id', 'recorded_at']
    ordering      = ['-date', 'metal']


@admin.register(BenchmarkValue)
class BenchmarkValueAdmin(admin.ModelAdmin):
    list_display  = ['category', 'subcategory', 'value_inr', 'unit',
                     'effective_from', 'effective_until', 'updated_at']
    list_filter   = ['category']
    search_fields = ['category', 'subcategory']
    readonly_fields = ['id', 'updated_at']


@admin.register(OracleNode)
class OracleNodeAdmin(admin.ModelAdmin):
    list_display  = ['node_name', 'node_address', 'status', 'uptime_percent', 'last_heartbeat']
    list_filter   = ['status']
    search_fields = ['node_name', 'node_address']
    readonly_fields = ['id', 'created_at']


@admin.register(PriceFeed)
class PriceFeedAdmin(admin.ModelAdmin):
    list_display  = ['feed_type', 'value', 'source_node', 'timestamp']
    list_filter   = ['feed_type']
    search_fields = ['feed_type', 'blockchain_tx_hash']
    readonly_fields = ['id', 'timestamp']
    ordering      = ['-timestamp']
