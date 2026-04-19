"""
irg_gic Models - Gold Investment Certificate with 3 Revenue Streams
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class GICCertificate(models.Model):
    """Gold Investment Certificate"""
    STATUS_CHOICES = [('ACTIVE','Active'),('MATURED','Matured'),('REDEEMED','Redeemed')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    holder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='gic_certificates')
    
    certificate_number = models.CharField(max_length=50, unique=True)
    investment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    gold_equivalent_grams = models.DecimalField(max_digits=10, decimal_places=4)
    benchmark_at_issue = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    
    # 3 Revenue Streams tracking
    stream1_corpus_returns = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    stream2_trading_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    stream3_appreciation = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    blockchain_id = models.CharField(max_length=66, unique=True)
    issuance_tx_hash = models.CharField(max_length=66)
    
    issued_at = models.DateTimeField(auto_now_add=True)
    maturity_date = models.DateField()
    
    class Meta:
        db_table = 'irg_gic_certificate'

class GICRevenueDistribution(models.Model):
    """Revenue distribution record for GIC holders"""
    STREAM_CHOICES = [('CORPUS','Corpus Returns'),('TRADING','Trading Fees'),('APPRECIATION','Gold Appreciation')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(GICCertificate, on_delete=models.PROTECT, related_name='distributions')
    
    stream = models.CharField(max_length=15, choices=STREAM_CHOICES)
    period = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    distribution_tx_hash = models.CharField(max_length=66)
    distributed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'irg_gic_distribution'
