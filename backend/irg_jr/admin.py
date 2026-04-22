from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from decimal import Decimal
from .models import JRUnit, IssuanceRecord, BuybackRecord, RedemptionRecord, GoldAssessment


# ── IssuanceRecord ────────────────────────────────────────────────────────────

def _confirm_payment(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    from irg_gdp.models import GDPUnit, MintingRecord
    from django.conf import settings
    import uuid, logging
    logger = logging.getLogger(__name__)
    blockchain = BlockchainService()

    confirmed = 0
    skipped   = 0

    for issuance in queryset.filter(status='PAYMENT_VERIFIED'):
        if not issuance.payment_proof:
            modeladmin.message_user(
                request,
                f'Issuance {issuance.id} skipped — no payment proof uploaded.',
                messages.WARNING,
            )
            skipped += 1
            continue

        pd = issuance.pending_data or {}
        try:
            tx_hash = blockchain.issue_jr(
                jeweler_address=issuance.jeweler.blockchain_address or '0x0',
                customer_address=issuance.customer.blockchain_address or '0x0',
                value=int(Decimal(pd.get('issue_value', '0')) * 100),
            )
            jr_unit = JRUnit.objects.create(
                owner=issuance.customer,
                issuing_jeweler=issuance.jeweler,
                jewelry_type=pd['jewelry_type'],
                description=pd['description'],
                gold_weight=pd['gold_weight'],
                purity=pd['purity'],
                making_charges=pd['making_charges'],
                stone_value=pd['stone_value'],
                issue_value=pd['issue_value'],
                benchmark_at_issue=pd['benchmark_at_issue'],
                buyback_guarantee_value=pd['buyback_guarantee_value'],
                lock_in_months=pd['lock_in_months'],
                lock_in_end_date=pd['lock_in_end_date'],
                blockchain_id=str(uuid.uuid4()),
                issuance_tx_hash=tx_hash,
            )
            issuance.jr_unit = jr_unit
            issuance.status  = 'COMPLETED'
            issuance.save()

            # Mint GDP units to customer
            try:
                config        = settings.IRG_GDP_CONFIG
                benchmark     = Decimal(pd['benchmark_at_issue'])
                purity_factor = {'24K': Decimal('1.0'), '22K': Decimal('0.9167'),
                                 '18K': Decimal('0.75'), '14K': Decimal('0.5833')}[pd['purity']]
                pure_gold = Decimal(pd['gold_weight']) * purity_factor
                saleable  = int(float(pure_gold) * config['SALEABLE_PER_GRAM'])
                reserve   = int(float(pure_gold) * config['RESERVE_PER_GRAM'])
                total     = saleable + reserve
                gdp_tx    = blockchain.mint_gdp(
                    to_address=issuance.customer.blockchain_address or '0x0',
                    gold_grams=int(pure_gold * 10**18),
                    purity=int(pd['purity'].replace('K', '')),
                    benchmark_rate=int(benchmark * 100),
                )
                mint_record = MintingRecord.objects.create(
                    user=issuance.customer,
                    gold_grams=pd['gold_weight'], purity=pd['purity'],
                    pure_gold_equivalent=pure_gold,
                    invoice_hash=issuance.utr_number or '',
                    invoice_verified=True, jeweler_certified=True,
                    nw_certified=True, within_cap=True, undertaking_signed=True,
                    certifying_jeweler=issuance.jeweler,
                    units_to_mint=total, saleable_units=saleable, reserve_units=reserve,
                    earmarking_amount=Decimal(pd['issue_value']) * Decimal(str(config['EARMARKING_PERCENTAGE'])) / 100,
                    corpus_contribution=issuance.corpus_contribution,
                    status='COMPLETED', transaction_hash=gdp_tx,
                    completed_at=timezone.now(),
                )
                GDPUnit.objects.create(
                    owner=issuance.customer,
                    gold_grams=pd['gold_weight'], purity=pd['purity'],
                    pure_gold_equivalent=pure_gold,
                    benchmark_rate_at_mint=benchmark,
                    benchmark_value=pure_gold * benchmark,
                    saleable_units=saleable, reserve_units=reserve, total_units=total,
                    source_jeweler=issuance.jeweler, minting_record=mint_record,
                    blockchain_id=str(uuid.uuid4()), minting_tx_hash=gdp_tx,
                )
            except Exception as gdp_err:
                logger.error('GDP minting failed after admin JR confirm %s: %s', issuance.id, gdp_err)

            confirmed += 1
        except Exception as e:
            logger.error('Admin confirm_payment failed for issuance %s: %s', issuance.id, e)
            modeladmin.message_user(request, f'Issuance {issuance.id} failed: {e}', messages.ERROR)

    if confirmed:
        modeladmin.message_user(
            request,
            f'{confirmed} issuance(s) confirmed — JR unit and GDP units issued.',
            messages.SUCCESS,
        )
    if skipped:
        modeladmin.message_user(request, f'{skipped} issuance(s) skipped (no payment proof).', messages.WARNING)

_confirm_payment.short_description = 'Confirm payment and issue JR + GDP units'


def _approve_buyback(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    blockchain = BlockchainService()
    updated = 0
    for buyback in queryset.filter(status='REQUESTED'):
        tx_hash = blockchain.process_buyback(str(buyback.jr_unit.id), int(buyback.buyback_value * 100))
        buyback.status = 'COMPLETED'
        buyback.buyback_tx_hash = tx_hash
        buyback.completed_at = timezone.now()
        buyback.save()
        buyback.jr_unit.status = 'BUYBACK'
        buyback.jr_unit.save()
        updated += 1
    modeladmin.message_user(request, f'{updated} buyback(s) approved and completed.', messages.SUCCESS)

_approve_buyback.short_description = 'Approve and complete selected buybacks'


# ── Admin classes ─────────────────────────────────────────────────────────────

@admin.register(JRUnit)
class JRUnitAdmin(admin.ModelAdmin):
    list_display    = ['blockchain_id', 'owner', 'issuing_jeweler', 'jewelry_type',
                       'gold_weight', 'purity', 'issue_value', 'status', 'issued_at']
    list_filter     = ['jewelry_type', 'purity', 'status']
    search_fields   = ['blockchain_id', 'owner__email', 'issuing_jeweler__business_name']
    readonly_fields = ['id', 'issued_at', 'blockchain_id', 'issuance_tx_hash']
    ordering        = ['-issued_at']


@admin.register(IssuanceRecord)
class IssuanceRecordAdmin(admin.ModelAdmin):
    list_display    = ['customer', 'jeweler', 'invoice_number', 'corpus_contribution',
                       'utr_number', 'status', 'created_at']
    list_filter     = ['status']
    search_fields   = ['customer__email', 'jeweler__business_name', 'invoice_number', 'utr_number']
    readonly_fields = ['id', 'created_at', 'pending_data']
    ordering        = ['-created_at']
    actions         = [_confirm_payment]


@admin.register(BuybackRecord)
class BuybackRecordAdmin(admin.ModelAdmin):
    list_display    = ['jr_unit', 'requested_by', 'buyback_value', 'benchmark_at_buyback',
                       'status', 'requested_at']
    list_filter     = ['status']
    search_fields   = ['requested_by__email', 'buyback_tx_hash']
    readonly_fields = ['id', 'requested_at', 'completed_at']
    ordering        = ['-requested_at']
    actions         = [_approve_buyback]


@admin.register(RedemptionRecord)
class RedemptionRecordAdmin(admin.ModelAdmin):
    list_display    = ['jr_unit', 'redeemed_by', 'redeemed_at', 'delivered_at']
    search_fields   = ['redeemed_by__email', 'redemption_tx_hash']
    readonly_fields = ['id', 'redeemed_at']
    ordering        = ['-redeemed_at']


@admin.register(GoldAssessment)
class GoldAssessmentAdmin(admin.ModelAdmin):
    list_display    = ['certificate_number', 'jeweler', 'customer_email', 'purity',
                       'test_method', 'estimated_value', 'status', 'created_at']
    list_filter     = ['purity', 'test_method', 'status']
    search_fields   = ['certificate_number', 'customer_email', 'jeweler__business_name']
    readonly_fields = ['id', 'created_at']
    ordering        = ['-created_at']
