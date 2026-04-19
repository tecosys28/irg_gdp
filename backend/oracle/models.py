"""
Oracle Models - LBMA Rates, Benchmark Values, Price Feeds
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class LBMARate(models.Model):
    """LBMA Precious Metals Rates"""
    METAL_CHOICES = [('XAU','Gold'),('XAG','Silver'),('XPT','Platinum'),('XPD','Palladium'),('XRH','Rhodium'),('XIR','Iridium'),('XRU','Ruthenium')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metal = models.CharField(max_length=5, choices=METAL_CHOICES)
    date = models.DateField()
    
    am_fix_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    pm_fix_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    inr_per_gram = models.DecimalField(max_digits=12, decimal_places=2)
    
    change_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    source = models.CharField(max_length=50, default='LBMA')
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'oracle_lbma_rate'
        unique_together = ['metal', 'date']
        ordering = ['-date', 'metal']

class BenchmarkValue(models.Model):
    """Benchmark values for various FTR categories"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=50)
    subcategory = models.CharField(max_length=50, blank=True)
    
    value_inr = models.DecimalField(max_digits=15, decimal_places=2)
    unit = models.CharField(max_length=20)
    
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'oracle_benchmark'

class OracleNode(models.Model):
    """Oracle node status tracking"""
    STATUS_CHOICES = [('ONLINE','Online'),('OFFLINE','Offline'),('SYNCING','Syncing')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    node_name = models.CharField(max_length=100)
    node_address = models.CharField(max_length=66)
    endpoint_url = models.URLField()
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OFFLINE')
    last_heartbeat = models.DateTimeField(null=True)
    uptime_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'oracle_node'

class PriceFeed(models.Model):
    """Real-time price feed records"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feed_type = models.CharField(max_length=50)
    value = models.DecimalField(max_digits=15, decimal_places=4)
    source_node = models.ForeignKey(OracleNode, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField()
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    class Meta:
        db_table = 'oracle_price_feed'
        ordering = ['-timestamp']
