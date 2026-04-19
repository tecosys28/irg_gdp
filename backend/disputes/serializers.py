"""Disputes Serializers"""
from rest_framework import serializers
from .models import *

class DisputeSerializer(serializers.ModelSerializer):
    filed_by_name = serializers.CharField(source='filed_by.get_full_name', read_only=True)
    against_name = serializers.CharField(source='against.get_full_name', read_only=True)
    class Meta:
        model = Dispute
        fields = '__all__'
        read_only_fields = ['case_number', 'filed_by', 'status', 'assigned_ombudsman', 'resolved_at']

class ResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resolution
        fields = '__all__'

class CompensationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Compensation
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'

class FileDisputeSerializer(serializers.Serializer):
    against_email = serializers.EmailField()
    category = serializers.ChoiceField(choices=[('BUYBACK','Buyback'),('QUALITY','Quality'),('DELIVERY','Delivery'),('PAYMENT','Payment'),('OTHER','Other')])
    subject = serializers.CharField(max_length=200)
    description = serializers.CharField()
    amount_in_dispute = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
