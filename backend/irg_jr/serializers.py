"""irg_jr Serializers - Jewellery Rights"""
from rest_framework import serializers
from .models import *

class JRUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = JRUnit
        fields = '__all__'

class IssuanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssuanceRecord
        fields = '__all__'

class BuybackRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuybackRecord
        fields = '__all__'
        read_only_fields = ['requested_by', 'status', 'buyback_tx_hash', 'completed_at']

class RedemptionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionRecord
        fields = '__all__'

class IssueJRRequestSerializer(serializers.Serializer):
    customer_email = serializers.EmailField()
    jewelry_type = serializers.ChoiceField(choices=[('NEW','New'),('OLD','Old'),('REMADE','Remade')])
    description = serializers.CharField()
    gold_weight = serializers.DecimalField(max_digits=10, decimal_places=4)
    purity = serializers.ChoiceField(choices=[('24K','24K'),('22K','22K'),('18K','18K'),('14K','14K')])
    making_charges = serializers.DecimalField(max_digits=12, decimal_places=2)
    stone_value = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_number = serializers.CharField()
