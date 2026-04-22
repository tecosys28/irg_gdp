from django.contrib import admin
from .models import Proposal, Vote, Parameter, GovernanceAction


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display  = ['title', 'proposer', 'category', 'status', 'votes_for',
                     'votes_against', 'voting_starts', 'voting_ends']
    list_filter   = ['category', 'status']
    search_fields = ['title', 'proposer__email', 'blockchain_id']
    readonly_fields = ['id', 'created_at']
    ordering      = ['-created_at']


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display  = ['proposal', 'voter', 'vote_for', 'voting_power', 'voted_at']
    list_filter   = ['vote_for']
    search_fields = ['proposal__title', 'voter__email', 'vote_tx_hash']
    readonly_fields = ['id', 'voted_at']


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display  = ['name', 'value', 'value_type', 'last_updated', 'updated_by_proposal']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'last_updated']


@admin.register(GovernanceAction)
class GovernanceActionAdmin(admin.ModelAdmin):
    list_display  = ['action_type', 'executed_by', 'proposal', 'executed_at']
    list_filter   = ['action_type']
    search_fields = ['executed_by__email', 'action_tx_hash']
    readonly_fields = ['id', 'executed_at']
    ordering      = ['-executed_at']
