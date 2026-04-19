"""Recall & DAC Serializers"""
from rest_framework import serializers
from .models import *

class RecallOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecallOrder
        fields = '__all__'
        read_only_fields = ['initiated_by', 'approved_by', 'status', 'recall_tx_hash']

class RecallAffectedUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecallAffectedUnit
        fields = '__all__'

class NodeAgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = NodeAgent
        fields = '__all__'
        read_only_fields = ['operator', 'status', 'last_heartbeat', 'uptime_percent']

class DACProposalSerializer(serializers.ModelSerializer):
    votes_list = serializers.SerializerMethodField()
    class Meta:
        model = DACProposal
        fields = '__all__'
        read_only_fields = ['proposer', 'status', 'votes_received', 'execution_tx_hash']
    
    def get_votes_list(self, obj):
        return DACVoteSerializer(obj.votes.all(), many=True).data

class DACVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DACVote
        fields = '__all__'

class EmergencyActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyAction
        fields = '__all__'

class InitiateRecallSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=[('FRAUD','Fraud'),('COMPLIANCE','Compliance'),('DISPUTE','Dispute'),('SECURITY','Security'),('LEGAL','Legal'),('EMERGENCY','Emergency')])
    description = serializers.CharField()
    target_unit_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    target_user_email = serializers.EmailField(required=False)
