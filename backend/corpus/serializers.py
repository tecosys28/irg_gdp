"""Corpus Fund Serializers"""
from rest_framework import serializers
from .models import *

class CorpusFundSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorpusFund
        fields = '__all__'

class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = '__all__'

class InvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investment
        fields = '__all__'

class SettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settlement
        fields = '__all__'
