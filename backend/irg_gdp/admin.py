from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import (GDPUnit, MintingRecord, EarmarkingRecord,
                     BonusAllocation, SwapRecord, TradeRecord, TransferRecord)


# ── MintingRecord actions ─────────────────────────────────────────────────────

def _execute_mint(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    from django.conf import settings
    from oracle.models import LBMARate
    from decimal import Decimal
    import uuid
    blockchain = BlockchainService()

    done = 0
    for record in queryset.filter(status='VERIFIED'):
        if not record.is_checklist_complete():
            modeladmin.message_user(
                request,
                f'Mint {record.id} skipped — 5-point checklist incomplete.',
                messages.WARNING,
            )
            continue
        try:
            latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
            benchmark = latest.inr_per_gram if latest else Decimal('6500')

            record.status = 'MINTING'
            record.save()

            tx_hash = blockchain.mint_gdp(
                to_address=record.user.blockchain_address or '0x0',
                gold_grams=int(record.pure_gold_equivalent * 10**18),
                purity=int(record.purity.replace('K', '')),
                benchmark_rate=int(benchmark * 100),
            )
            GDPUnit.objects.create(
                owner=record.user,
                gold_grams=record.gold_grams,
                purity=record.purity,
                pure_gold_equivalent=record.pure_gold_equivalent,
                benchmark_rate_at_mint=benchmark,
                benchmark_value=record.pure_gold_equivalent * benchmark,
                saleable_units=record.saleable_units,
                reserve_units=record.reserve_units,
                total_units=record.units_to_mint,
                source_jeweler=record.certifying_jeweler,
                minting_record=record,
                blockchain_id=str(uuid.uuid4()),
                minting_tx_hash=tx_hash,
            )
            record.status = 'COMPLETED'
            record.transaction_hash = tx_hash
            record.completed_at = timezone.now()
            record.save()
            done += 1
        except Exception as e:
            record.status = 'REJECTED'
            record.rejection_reason = str(e)
            record.save()
            modeladmin.message_user(request, f'Mint {record.id} failed: {e}', messages.ERROR)

    if done:
        modeladmin.message_user(request, f'{done} minting record(s) executed successfully.', messages.SUCCESS)

def _reject_mint(modeladmin, request, queryset):
    updated = queryset.exclude(status__in=['COMPLETED', 'REJECTED']).update(
        status='REJECTED', rejection_reason='Rejected by admin.'
    )
    modeladmin.message_user(request, f'{updated} minting record(s) rejected.', messages.WARNING)

def _approve_checklist(modeladmin, request, queryset):
    updated = 0
    for record in queryset.filter(status__in=['INITIATED', 'CHECKLIST_PENDING']):
        record.invoice_verified  = True
        record.jeweler_certified = True
        record.nw_certified      = True
        record.within_cap        = True
        record.undertaking_signed = True
        record.status = 'VERIFIED'
        record.save()
        updated += 1
    modeladmin.message_user(request, f'{updated} checklist(s) approved and marked VERIFIED.', messages.SUCCESS)

_execute_mint.short_description      = 'Execute mint for VERIFIED records'
_reject_mint.short_description       = 'Reject selected minting records'
_approve_checklist.short_description = 'Approve 5-point checklist and mark VERIFIED'


# ── EarmarkingRecord actions ──────────────────────────────────────────────────

def _release_earmark(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    blockchain = BlockchainService()
    updated = 0
    for earmark in queryset.filter(status='ACTIVE'):
        tx_hash = blockchain.release_earmark(str(earmark.id))
        earmark.status = 'RELEASED'
        earmark.released_at = timezone.now()
        earmark.release_tx_hash = tx_hash
        earmark.save()
        earmark.gdp_unit.status = 'ACTIVE'
        earmark.gdp_unit.save()
        updated += 1
    modeladmin.message_user(request, f'{updated} earmark(s) released.', messages.SUCCESS)

_release_earmark.short_description = 'Release selected earmarks'


# ── BonusAllocation actions ───────────────────────────────────────────────────

def _approve_bonus(modeladmin, request, queryset):
    updated = queryset.filter(status='CALCULATED').update(status='APPROVED')
    modeladmin.message_user(request, f'{updated} bonus allocation(s) approved.', messages.SUCCESS)

def _distribute_bonus(modeladmin, request, queryset):
    updated = 0
    for bonus in queryset.filter(status='APPROVED'):
        bonus.status = 'DISTRIBUTED'
        bonus.distributed_at = timezone.now()
        bonus.save()
        updated += 1
    modeladmin.message_user(request, f'{updated} bonus(es) marked as distributed.', messages.SUCCESS)

_approve_bonus.short_description    = 'Approve selected bonus allocations'
_distribute_bonus.short_description = 'Mark selected bonuses as distributed'


# ── Admin classes ─────────────────────────────────────────────────────────────

@admin.register(GDPUnit)
class GDPUnitAdmin(admin.ModelAdmin):
    list_display    = ['blockchain_id', 'owner', 'gold_grams', 'purity', 'pure_gold_equivalent',
                       'total_units', 'status', 'minted_at']
    list_filter     = ['purity', 'status']
    search_fields   = ['blockchain_id', 'owner__email', 'minting_tx_hash']
    readonly_fields = ['id', 'minted_at', 'updated_at']
    ordering        = ['-minted_at']


@admin.register(MintingRecord)
class MintingRecordAdmin(admin.ModelAdmin):
    list_display    = ['user', 'gold_grams', 'purity', 'units_to_mint', 'status',
                       'invoice_verified', 'jeweler_certified', 'nw_certified',
                       'within_cap', 'undertaking_signed', 'created_at']
    list_filter     = ['status', 'purity', 'invoice_verified', 'jeweler_certified']
    search_fields   = ['user__email', 'invoice_hash', 'transaction_hash']
    readonly_fields = ['id', 'created_at', 'completed_at', 'transaction_hash']
    ordering        = ['-created_at']
    actions         = [_approve_checklist, _execute_mint, _reject_mint]


@admin.register(EarmarkingRecord)
class EarmarkingRecordAdmin(admin.ModelAdmin):
    list_display    = ['user', 'gdp_unit', 'amount', 'rate_percent', 'status',
                       'earmarked_at', 'release_date']
    list_filter     = ['status']
    search_fields   = ['user__email', 'earmark_tx_hash']
    readonly_fields = ['id', 'earmarked_at', 'released_at']
    ordering        = ['-earmarked_at']
    actions         = [_release_earmark]


@admin.register(BonusAllocation)
class BonusAllocationAdmin(admin.ModelAdmin):
    list_display    = ['user', 'amount', 'source', 'period', 'status', 'allocated_at']
    list_filter     = ['source', 'status']
    search_fields   = ['user__email', 'period']
    readonly_fields = ['id', 'allocated_at', 'distributed_at']
    ordering        = ['-allocated_at']
    actions         = [_approve_bonus, _distribute_bonus]


@admin.register(SwapRecord)
class SwapRecordAdmin(admin.ModelAdmin):
    list_display    = ['user', 'gdp_units_swapped', 'gdp_value_at_swap', 'ftr_category',
                       'ftr_units_received', 'status', 'initiated_at']
    list_filter     = ['ftr_category', 'status']
    search_fields   = ['user__email', 'swap_tx_hash']
    readonly_fields = ['id', 'initiated_at', 'completed_at']
    ordering        = ['-initiated_at']


@admin.register(TradeRecord)
class TradeRecordAdmin(admin.ModelAdmin):
    list_display    = ['trade_type', 'user', 'counterparty', 'units', 'price_per_unit',
                       'total_value', 'status', 'created_at']
    list_filter     = ['trade_type', 'status']
    search_fields   = ['user__email', 'counterparty__email', 'trade_tx_hash']
    readonly_fields = ['id', 'created_at', 'executed_at']
    ordering        = ['-created_at']


@admin.register(TransferRecord)
class TransferRecordAdmin(admin.ModelAdmin):
    list_display    = ['from_user', 'to_user', 'gdp_unit', 'transfer_type', 'transferred_at']
    list_filter     = ['transfer_type']
    search_fields   = ['from_user__email', 'to_user__email', 'transfer_tx_hash']
    readonly_fields = ['id', 'transferred_at']
    ordering        = ['-transferred_at']
