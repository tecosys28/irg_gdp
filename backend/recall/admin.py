from django.contrib import admin
from .models import (RecallOrder, RecallAffectedUnit, NodeAgent,
                     DACProposal, DACVote, EmergencyAction)


@admin.register(RecallOrder)
class RecallOrderAdmin(admin.ModelAdmin):
    list_display  = ['reason', 'initiated_by', 'approved_by', 'status',
                     'initiated_at', 'completed_at']
    list_filter   = ['reason', 'status']
    search_fields = ['initiated_by__email', 'target_user__email', 'recall_tx_hash']
    readonly_fields = ['id', 'initiated_at', 'approved_at', 'completed_at']
    ordering      = ['-initiated_at']


@admin.register(RecallAffectedUnit)
class RecallAffectedUnitAdmin(admin.ModelAdmin):
    list_display  = ['recall_order', 'unit_type', 'unit_id', 'original_owner',
                     'original_value', 'processed']
    list_filter   = ['unit_type', 'processed']
    search_fields = ['original_owner__email']
    readonly_fields = ['id', 'processed_at']


@admin.register(NodeAgent)
class NodeAgentAdmin(admin.ModelAdmin):
    list_display  = ['name', 'role', 'node_address', 'region', 'operator',
                     'status', 'uptime_percent', 'last_heartbeat']
    list_filter   = ['role', 'status', 'region']
    search_fields = ['name', 'node_address', 'operator__email']
    readonly_fields = ['id', 'registered_at']


@admin.register(DACProposal)
class DACProposalAdmin(admin.ModelAdmin):
    list_display  = ['title', 'proposal_type', 'proposer', 'status',
                     'votes_required', 'votes_received', 'created_at']
    list_filter   = ['proposal_type', 'status']
    search_fields = ['title', 'proposer__email', 'blockchain_id']
    readonly_fields = ['id', 'created_at', 'executed_at']
    ordering      = ['-created_at']


@admin.register(DACVote)
class DACVoteAdmin(admin.ModelAdmin):
    list_display  = ['proposal', 'node', 'voter', 'approve', 'voted_at']
    list_filter   = ['approve']
    search_fields = ['voter__email', 'vote_tx_hash']
    readonly_fields = ['id', 'voted_at']


@admin.register(EmergencyAction)
class EmergencyActionAdmin(admin.ModelAdmin):
    list_display  = ['action', 'initiated_by', 'active', 'reverted', 'executed_at']
    list_filter   = ['action', 'active', 'reverted']
    search_fields = ['initiated_by__email', 'action_tx_hash']
    readonly_fields = ['id', 'executed_at', 'reverted_at']
    ordering      = ['-executed_at']
