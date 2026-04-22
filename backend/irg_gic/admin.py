from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import GICCertificate, GICRevenueDistribution, HouseholdRegistration, GICRedemption


# ── GICRedemption actions ─────────────────────────────────────────────────────

def _approve_redemption(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    blockchain = BlockchainService()
    done = 0
    for redemption in queryset.filter(status='REQUESTED'):
        try:
            # Mark processing first
            redemption.status = 'PROCESSING'
            redemption.save()

            tx_hash = blockchain.corpus_settlement(
                fund_id=str(redemption.certificate.id),
                beneficiary=redemption.redeemed_by.blockchain_address or '0x0',
                amount=int(redemption.redemption_value * 100),
            )
            redemption.redemption_tx_hash = tx_hash
            redemption.status = 'COMPLETED'
            redemption.completed_at = timezone.now()
            redemption.save()

            redemption.certificate.status = 'REDEEMED'
            redemption.certificate.save()
            done += 1
        except Exception as e:
            redemption.status = 'REJECTED'
            redemption.save()
            modeladmin.message_user(request, f'Redemption {redemption.id} failed: {e}', messages.ERROR)

    if done:
        modeladmin.message_user(request, f'{done} GIC redemption(s) completed.', messages.SUCCESS)

def _reject_redemption(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['REQUESTED', 'PROCESSING']).update(status='REJECTED')
    modeladmin.message_user(request, f'{updated} GIC redemption(s) rejected.', messages.WARNING)

_approve_redemption.short_description = 'Approve and complete selected GIC redemptions'
_reject_redemption.short_description  = 'Reject selected GIC redemptions'


# ── GICCertificate actions ────────────────────────────────────────────────────

def _mark_matured(modeladmin, request, queryset):
    from django.utils import timezone as tz
    today = tz.now().date()
    updated = queryset.filter(status='ACTIVE', maturity_date__lte=today).update(status='MATURED')
    modeladmin.message_user(request, f'{updated} certificate(s) marked as matured.', messages.SUCCESS)

_mark_matured.short_description = 'Mark past-maturity certificates as MATURED'


# ── Admin classes ─────────────────────────────────────────────────────────────

@admin.register(GICCertificate)
class GICCertificateAdmin(admin.ModelAdmin):
    list_display    = ['certificate_number', 'holder', 'investment_amount', 'gold_equivalent_grams',
                       'status', 'maturity_date', 'issued_at']
    list_filter     = ['status']
    search_fields   = ['certificate_number', 'holder__email', 'blockchain_id']
    readonly_fields = ['id', 'issued_at', 'blockchain_id', 'issuance_tx_hash']
    ordering        = ['-issued_at']
    actions         = [_mark_matured]


@admin.register(GICRevenueDistribution)
class GICRevenueDistributionAdmin(admin.ModelAdmin):
    list_display    = ['certificate', 'stream', 'period', 'amount', 'distributed_at']
    list_filter     = ['stream']
    search_fields   = ['certificate__certificate_number', 'period', 'distribution_tx_hash']
    readonly_fields = ['id', 'distributed_at']
    ordering        = ['-distributed_at']


@admin.register(HouseholdRegistration)
class HouseholdRegistrationAdmin(admin.ModelAdmin):
    list_display    = ['licensee', 'household_user', 'commission_rate', 'status', 'registered_at']
    list_filter     = ['status']
    search_fields   = ['household_user__email', 'licensee__entity_name']
    readonly_fields = ['id', 'registered_at']


@admin.register(GICRedemption)
class GICRedemptionAdmin(admin.ModelAdmin):
    list_display    = ['certificate', 'redeemed_by', 'redemption_value', 'status', 'requested_at']
    list_filter     = ['status']
    search_fields   = ['certificate__certificate_number', 'redeemed_by__email', 'redemption_tx_hash']
    readonly_fields = ['id', 'requested_at', 'completed_at', 'redemption_tx_hash']
    ordering        = ['-requested_at']
    actions         = [_approve_redemption, _reject_redemption]
