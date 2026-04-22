"""irg_gic Serializers - Gold Investment Certificate"""
from rest_framework import serializers
from .models import *

class GICCertificateSerializer(serializers.ModelSerializer):
    total_returns = serializers.SerializerMethodField()
    class Meta:
        model = GICCertificate
        fields = '__all__'
    def get_total_returns(self, obj):
        return str(obj.stream1_corpus_returns + obj.stream2_trading_fees + obj.stream3_appreciation)

class GICRevenueDistributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GICRevenueDistribution
        fields = '__all__'

class HouseholdRegistrationSerializer(serializers.ModelSerializer):
    household_email = serializers.CharField(source='household_user.email', read_only=True)
    class Meta:
        model = HouseholdRegistration
        fields = '__all__'
        read_only_fields = ['licensee', 'registered_at']

class GICRedemptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GICRedemption
        fields = '__all__'
        read_only_fields = ['redeemed_by', 'redemption_value', 'status', 'redemption_tx_hash', 'requested_at', 'completed_at']
