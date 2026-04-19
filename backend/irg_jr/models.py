"""
irg_jr Models - Tradable Jewellery Rights with No-Loss Buyback
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class JRUnit(models.Model):
    """Jewellery Rights Unit - No-loss buyback protected"""
    STATUS_CHOICES = [('ACTIVE','Active'),('RETURNED','Returned'),('BUYBACK','Buyback Completed'),('EXPIRED','Expired')]
    JEWELRY_TYPES = [('NEW','New Jewelry'),('OLD','Old Jewelry'),('REMADE','Remade Jewelry')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='jr_units')
    issuing_jeweler = models.ForeignKey('core.JewelerProfile', on_delete=models.PROTECT, related_name='issued_jr_units')
    
    jewelry_type = models.CharField(max_length=10, choices=JEWELRY_TYPES)
    description = models.TextField()
    gold_weight = models.DecimalField(max_digits=10, decimal_places=4)
    purity = models.CharField(max_length=5)
    making_charges = models.DecimalField(max_digits=12, decimal_places=2)
    stone_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    issue_value = models.DecimalField(max_digits=15, decimal_places=2)
    benchmark_at_issue = models.DecimalField(max_digits=12, decimal_places=2)
    buyback_guarantee_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    lock_in_months = models.PositiveIntegerField()
    lock_in_end_date = models.DateField()
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    blockchain_id = models.CharField(max_length=66, unique=True)
    issuance_tx_hash = models.CharField(max_length=66)
    
    issued_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'irg_jr_unit'

class IssuanceRecord(models.Model):
    """Record of JR issuance"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jr_unit = models.OneToOneField(JRUnit, on_delete=models.PROTECT, related_name='issuance_record')
    jeweler = models.ForeignKey('core.JewelerProfile', on_delete=models.PROTECT)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    invoice_number = models.CharField(max_length=50)
    invoice_file = models.FileField(upload_to='jr_invoices/')
    corpus_contribution = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'irg_jr_issuance'

class BuybackRecord(models.Model):
    """Record of JR buyback"""
    STATUS_CHOICES = [('REQUESTED','Requested'),('APPROVED','Approved'),('COMPLETED','Completed'),('REJECTED','Rejected')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jr_unit = models.ForeignKey(JRUnit, on_delete=models.PROTECT, related_name='buyback_records')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    buyback_value = models.DecimalField(max_digits=15, decimal_places=2)
    benchmark_at_buyback = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='REQUESTED')
    buyback_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = 'irg_jr_buyback'

class RedemptionRecord(models.Model):
    """Record of JR redemption for physical jewelry"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jr_unit = models.ForeignKey(JRUnit, on_delete=models.PROTECT, related_name='redemption_records')
    redeemed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    delivery_address = models.TextField()
    redemption_tx_hash = models.CharField(max_length=66)
    redeemed_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = 'irg_jr_redemption'
