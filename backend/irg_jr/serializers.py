"""irg_jr Serializers - Jewellery Rights"""
from rest_framework import serializers
from .models import *

class JRUnitSerializer(serializers.ModelSerializer):
    owner_email = serializers.SerializerMethodField()

    class Meta:
        model = JRUnit
        fields = '__all__'

    def get_owner_email(self, obj):
        return obj.owner.email if obj.owner_id else '—'

class IssuanceRecordSerializer(serializers.ModelSerializer):
    customer_email = serializers.SerializerMethodField()

    class Meta:
        model = IssuanceRecord
        fields = '__all__'
        read_only_fields = ['jeweler', 'customer', 'corpus_contribution', 'status',
                            'jr_unit', 'pending_data', 'created_at']

    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer_id else '—'

class BuybackRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuybackRecord
        fields = '__all__'
        read_only_fields = ['requested_by', 'status', 'buyback_tx_hash', 'completed_at']

class RedemptionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionRecord
        fields = '__all__'

# ── Request bodies ──────────────────────────────────────────────────────────

class InitiateIssuanceSerializer(serializers.Serializer):
    """Step 1: jeweler submits jewellery details → gets bank account + corpus amount."""
    customer_email = serializers.EmailField()
    jewelry_type = serializers.ChoiceField(choices=[('NEW', 'New'), ('OLD', 'Old'), ('REMADE', 'Remade')])
    description = serializers.CharField()
    gold_weight = serializers.DecimalField(max_digits=10, decimal_places=4)
    purity = serializers.ChoiceField(choices=[('24K', '24K'), ('22K', '22K'), ('18K', '18K'), ('14K', '14K')])
    making_charges = serializers.DecimalField(max_digits=12, decimal_places=2)
    stone_value = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_number = serializers.CharField()

class VerifyPaymentSerializer(serializers.Serializer):
    """Step 2: jeweler submits UTR + mandatory payment proof screenshot."""
    utr_number = serializers.CharField(max_length=50)
    payment_proof = serializers.FileField(required=True)

class GoldAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoldAssessment
        fields = '__all__'
        read_only_fields = ['jeweler', 'certificate_number', 'estimated_value', 'benchmark_used', 'status', 'created_at']

class GoldAssessmentRequestSerializer(serializers.Serializer):
    customer_email = serializers.EmailField()
    item_description = serializers.CharField()
    estimated_weight = serializers.DecimalField(max_digits=10, decimal_places=4)
    purity = serializers.ChoiceField(choices=[('24K','24K'),('22K','22K'),('18K','18K'),('14K','14K')])
    test_method = serializers.ChoiceField(choices=['XRF','ACID','FIRE','DENSITY'], default='XRF')
    assessment_notes = serializers.CharField(required=False, allow_blank=True)

# kept for backward-compat with the old single-step `issue` action
class IssueJRRequestSerializer(serializers.Serializer):
    customer_email = serializers.EmailField()
    jewelry_type = serializers.ChoiceField(choices=[('NEW', 'New'), ('OLD', 'Old'), ('REMADE', 'Remade')])
    description = serializers.CharField()
    gold_weight = serializers.DecimalField(max_digits=10, decimal_places=4)
    purity = serializers.ChoiceField(choices=[('24K', '24K'), ('22K', '22K'), ('18K', '18K'), ('14K', '14K')])
    making_charges = serializers.DecimalField(max_digits=12, decimal_places=2)
    stone_value = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_number = serializers.CharField()
