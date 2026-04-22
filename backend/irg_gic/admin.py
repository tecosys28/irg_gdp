from django.contrib import admin
from .models import GICCertificate, GICRevenueDistribution, HouseholdRegistration, GICRedemption


@admin.register(GICCertificate)
class GICCertificateAdmin(admin.ModelAdmin):
    list_display  = ['certificate_number', 'holder', 'investment_amount', 'gold_equivalent_grams',
                     'status', 'maturity_date', 'issued_at']
    list_filter   = ['status']
    search_fields = ['certificate_number', 'holder__email', 'blockchain_id']
    readonly_fields = ['id', 'issued_at', 'blockchain_id', 'issuance_tx_hash']
    ordering      = ['-issued_at']


@admin.register(GICRevenueDistribution)
class GICRevenueDistributionAdmin(admin.ModelAdmin):
    list_display  = ['certificate', 'stream', 'period', 'amount', 'distributed_at']
    list_filter   = ['stream']
    search_fields = ['certificate__certificate_number', 'period', 'distribution_tx_hash']
    readonly_fields = ['id', 'distributed_at']
    ordering      = ['-distributed_at']


@admin.register(HouseholdRegistration)
class HouseholdRegistrationAdmin(admin.ModelAdmin):
    list_display  = ['licensee', 'household_user', 'commission_rate', 'status', 'registered_at']
    list_filter   = ['status']
    search_fields = ['household_user__email', 'licensee__entity_name']
    readonly_fields = ['id', 'registered_at']


@admin.register(GICRedemption)
class GICRedemptionAdmin(admin.ModelAdmin):
    list_display  = ['certificate', 'redeemed_by', 'redemption_value', 'status', 'requested_at']
    list_filter   = ['status']
    search_fields = ['certificate__certificate_number', 'redeemed_by__email', 'redemption_tx_hash']
    readonly_fields = ['id', 'requested_at', 'completed_at']
    ordering      = ['-requested_at']
