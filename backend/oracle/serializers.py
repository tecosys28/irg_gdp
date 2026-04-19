"""Oracle Serializers - LBMA Rates, Benchmarks"""
from rest_framework import serializers
from .models import *

class LBMARateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LBMARate
        fields = '__all__'

class BenchmarkValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = BenchmarkValue
        fields = '__all__'

class OracleNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OracleNode
        fields = '__all__'

class PriceFeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceFeed
        fields = '__all__'

class LBMAUpdateSerializer(serializers.Serializer):
    metal = serializers.ChoiceField(choices=[('XAU','Gold'),('XAG','Silver'),('XPT','Platinum'),('XPD','Palladium'),('XRH','Rhodium'),('XIR','Iridium'),('XRU','Ruthenium')])
    date = serializers.DateField()
    am_fix_usd = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    pm_fix_usd = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    inr_per_gram = serializers.DecimalField(max_digits=12, decimal_places=2)
