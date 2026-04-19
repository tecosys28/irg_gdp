"""Governance Serializers"""
from rest_framework import serializers
from .models import *

class ProposalSerializer(serializers.ModelSerializer):
    proposer_name = serializers.CharField(source='proposer.get_full_name', read_only=True)
    vote_percentage = serializers.SerializerMethodField()
    class Meta:
        model = Proposal
        fields = '__all__'
    def get_vote_percentage(self, obj):
        total = obj.votes_for + obj.votes_against
        if total == 0:
            return 0
        return round((obj.votes_for / total) * 100, 2)

class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = '__all__'
        read_only_fields = ['voter', 'vote_tx_hash', 'voted_at']

class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = '__all__'

class GovernanceActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GovernanceAction
        fields = '__all__'

class CastVoteSerializer(serializers.Serializer):
    proposal_id = serializers.UUIDField()
    vote_for = serializers.BooleanField()
