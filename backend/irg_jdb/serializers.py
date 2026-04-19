"""irg_jdb Serializers - Designer Bank"""
from rest_framework import serializers
from .models import *

class DesignSerializer(serializers.ModelSerializer):
    designer_name = serializers.CharField(source='designer.display_name', read_only=True)
    class Meta:
        model = Design
        fields = '__all__'
        read_only_fields = ['designer', 'status', 'copyright_hash', 'copyright_tx_hash']

class DesignOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignOrder
        fields = '__all__'
        read_only_fields = ['status', 'order_tx_hash', 'completed_at']

class RoyaltyPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoyaltyPayment
        fields = '__all__'

class CopyrightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Copyright
        fields = '__all__'
