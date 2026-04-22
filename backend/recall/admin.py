from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import (RecallOrder, RecallAffectedUnit, NodeAgent,
                     DACProposal, DACVote, EmergencyAction)


# ── RecallOrder actions ───────────────────────────────────────────────────────

def _approve_recall(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    blockchain = BlockchainService()
    done = 0
    for order in queryset.filter(status='INITIATED'):
        try:
            unit_ids = order.target_units or []
            tx_hash  = blockchain.recall_units(unit_ids or str(order.id), order.reason)
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.status      = 'APPROVED'
            order.recall_tx_hash = tx_hash
            order.save()
            done += 1
        except Exception as e:
            modeladmin.message_user(request, f'Recall {order.id} failed: {e}', messages.ERROR)
    if done:
        modeladmin.message_user(request, f'{done} recall order(s) approved.', messages.SUCCESS)

def _cancel_recall(modeladmin, request, queryset):
    updated = queryset.exclude(status__in=['COMPLETED', 'CANCELLED']).update(status='CANCELLED')
    modeladmin.message_user(request, f'{updated} recall order(s) cancelled.', messages.WARNING)

def _mark_recall_complete(modeladmin, request, queryset):
    updated = queryset.filter(status='EXECUTING').update(
        status='COMPLETED', completed_at=timezone.now()
    )
    modeladmin.message_user(request, f'{updated} recall order(s) marked complete.', messages.SUCCESS)

_approve_recall.short_description       = 'Approve and submit selected recall orders on-chain'
_cancel_recall.short_description        = 'Cancel selected recall orders'
_mark_recall_complete.short_description = 'Mark EXECUTING recalls as COMPLETED'


# ── DACProposal actions ───────────────────────────────────────────────────────

def _open_dac_voting(modeladmin, request, queryset):
    updated = queryset.filter(status='PENDING').update(status='VOTING')
    modeladmin.message_user(request, f'{updated} DAC proposal(s) opened for voting.', messages.SUCCESS)

def _execute_dac_proposal(modeladmin, request, queryset):
    done = 0
    for proposal in queryset.filter(status='APPROVED'):
        proposal.status = 'EXECUTED'
        proposal.executed_at = timezone.now()
        proposal.save()
        done += 1
    modeladmin.message_user(request, f'{done} DAC proposal(s) executed.', messages.SUCCESS)

_open_dac_voting.short_description    = 'Open selected proposals for voting'
_execute_dac_proposal.short_description = 'Execute APPROVED DAC proposals'


# ── EmergencyAction actions ───────────────────────────────────────────────────

def _revert_emergency(modeladmin, request, queryset):
    updated = 0
    for action in queryset.filter(active=True, reverted=False):
        action.active = False
        action.reverted = True
        action.reverted_at = timezone.now()
        action.reverted_by = request.user
        action.save()
        updated += 1
    modeladmin.message_user(request, f'{updated} emergency action(s) reverted.', messages.SUCCESS)

_revert_emergency.short_description = 'Revert selected emergency actions'


# ── RecallAffectedUnit inline ─────────────────────────────────────────────────

class RecallAffectedUnitInline(admin.TabularInline):
    model  = RecallAffectedUnit
    extra  = 0
    fields = ['unit_type', 'unit_id', 'original_owner', 'original_value', 'processed']
    readonly_fields = ['processed_at']
    show_change_link = False


# ── Admin classes ─────────────────────────────────────────────────────────────

@admin.register(RecallOrder)
class RecallOrderAdmin(admin.ModelAdmin):
    list_display    = ['reason', 'initiated_by', 'approved_by', 'status',
                       'initiated_at', 'completed_at']
    list_filter     = ['reason', 'status']
    search_fields   = ['initiated_by__email', 'target_user__email', 'recall_tx_hash']
    readonly_fields = ['id', 'initiated_at', 'approved_at', 'completed_at', 'recall_tx_hash']
    ordering        = ['-initiated_at']
    inlines         = [RecallAffectedUnitInline]
    actions         = [_approve_recall, _cancel_recall, _mark_recall_complete]


@admin.register(RecallAffectedUnit)
class RecallAffectedUnitAdmin(admin.ModelAdmin):
    list_display    = ['recall_order', 'unit_type', 'unit_id', 'original_owner',
                       'original_value', 'processed']
    list_filter     = ['unit_type', 'processed']
    search_fields   = ['original_owner__email']
    readonly_fields = ['id', 'processed_at']


@admin.register(NodeAgent)
class NodeAgentAdmin(admin.ModelAdmin):
    list_display    = ['name', 'role', 'node_address', 'region', 'operator',
                       'status', 'uptime_percent', 'last_heartbeat']
    list_filter     = ['role', 'status', 'region']
    search_fields   = ['name', 'node_address', 'operator__email']
    readonly_fields = ['id', 'registered_at']


@admin.register(DACProposal)
class DACProposalAdmin(admin.ModelAdmin):
    list_display    = ['title', 'proposal_type', 'proposer', 'status',
                       'votes_required', 'votes_received', 'created_at']
    list_filter     = ['proposal_type', 'status']
    search_fields   = ['title', 'proposer__email', 'blockchain_id']
    readonly_fields = ['id', 'created_at', 'executed_at']
    ordering        = ['-created_at']
    actions         = [_open_dac_voting, _execute_dac_proposal]


@admin.register(DACVote)
class DACVoteAdmin(admin.ModelAdmin):
    list_display    = ['proposal', 'node', 'voter', 'approve', 'voted_at']
    list_filter     = ['approve']
    search_fields   = ['voter__email', 'vote_tx_hash']
    readonly_fields = ['id', 'voted_at']


@admin.register(EmergencyAction)
class EmergencyActionAdmin(admin.ModelAdmin):
    list_display    = ['action', 'initiated_by', 'active', 'reverted', 'executed_at']
    list_filter     = ['action', 'active', 'reverted']
    search_fields   = ['initiated_by__email', 'action_tx_hash']
    readonly_fields = ['id', 'executed_at', 'reverted_at', 'action_tx_hash']
    ordering        = ['-executed_at']
    actions         = [_revert_emergency]
