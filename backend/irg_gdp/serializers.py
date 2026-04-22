"""
IRG_GDP Serializers - Minting, Earmarking, Swap, Trade, Transfer
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import serializers
from .models import *
from core.serializers import UserSerializer

class GDPUnitSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    current_value = serializers.SerializerMethodField()
    
    class Meta:
        model = GDPUnit
        fields = '__all__'
    
    def get_current_value(self, obj):
        # Get latest LBMA rate
        from oracle.models import LBMARate
        latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        if latest:
            return str(obj.get_current_value(latest.inr_per_gram))
        return str(obj.benchmark_value)

class MintingRequestSerializer(serializers.ModelSerializer):
    remaining_cap_grams = serializers.SerializerMethodField()

    class Meta:
        model = MintingRecord
        fields = '__all__'
        read_only_fields = ['user', 'status', 'transaction_hash', 'completed_at',
                           'saleable_units', 'reserve_units', 'units_to_mint',
                           'earmarking_amount', 'corpus_contribution',
                           'pure_gold_equivalent', 'within_cap']

    def get_remaining_cap_grams(self, obj):
        from django.db.models import Sum
        from decimal import Decimal
        minted = MintingRecord.objects.filter(
            user=obj.user, status='COMPLETED'
        ).exclude(id=obj.id).aggregate(total=Sum('pure_gold_equivalent'))['total'] or Decimal('0')
        return str(Decimal('500') - minted)

class MintingChecklistSerializer(serializers.Serializer):
    """5-point checklist verification"""
    invoice_verified = serializers.BooleanField()
    jeweler_certified = serializers.BooleanField()
    nw_certified = serializers.BooleanField()
    within_cap = serializers.BooleanField()
    undertaking_signed = serializers.BooleanField()
    certifying_jeweler_id = serializers.UUIDField(required=False)

class EarmarkingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EarmarkingRecord
        fields = '__all__'
        read_only_fields = ['user', 'status', 'earmark_tx_hash', 'release_tx_hash']

class SwapSerializer(serializers.ModelSerializer):
    class Meta:
        model = SwapRecord
        fields = '__all__'
        read_only_fields = ['user', 'status', 'swap_tx_hash', 'gdp_value_at_swap']

class SwapRequestSerializer(serializers.Serializer):
    gdp_unit_ids = serializers.ListField(child=serializers.UUIDField())
    ftr_category = serializers.ChoiceField(choices=[
        ('Healthcare', 'Healthcare'), ('Education', 'Education'), ('Travel', 'Travel'),
        ('Hospitality', 'Hospitality'), ('Real Estate', 'Real Estate'), ('Automobile', 'Automobile'),
        ('Electronics', 'Electronics'), ('Fashion', 'Fashion'), ('Food & Beverage', 'Food & Beverage'),
        ('Entertainment', 'Entertainment'), ('Fitness', 'Fitness'), ('Insurance', 'Insurance'),
        # ... 45+ categories
    ])

class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeRecord
        fields = '__all__'
        read_only_fields = ['user', 'status', 'trade_tx_hash', 'total_value', 'executed_at']

class TradeRequestSerializer(serializers.Serializer):
    trade_type = serializers.ChoiceField(choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    units = serializers.IntegerField(min_value=1)
    price_per_unit = serializers.DecimalField(max_digits=12, decimal_places=2)

class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRecord
        fields = '__all__'
        read_only_fields = ['from_user', 'transfer_tx_hash', 'transferred_at']

class TransferRequestSerializer(serializers.Serializer):
    gdp_unit_id = serializers.UUIDField()
    to_email = serializers.EmailField()
    transfer_type = serializers.ChoiceField(choices=[
        ('GIFT', 'Gift'), ('SPONSOR', 'Sponsorship'), ('INHERITANCE', 'Inheritance')
    ])
    message = serializers.CharField(required=False, allow_blank=True)

class BonusAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonusAllocation
        fields = '__all__'
