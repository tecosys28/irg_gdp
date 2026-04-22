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
    """Record of JR issuance — two-step: initiate → verify payment → issue JR unit"""
    STATUS_CHOICES = [
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('PAYMENT_VERIFIED', 'Payment Verified'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jr_unit = models.OneToOneField(
        JRUnit, on_delete=models.PROTECT, related_name='issuance_record',
        null=True, blank=True,
    )
    jeweler = models.ForeignKey('core.JewelerProfile', on_delete=models.PROTECT)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    invoice_number = models.CharField(max_length=50)
    invoice_file = models.FileField(upload_to='jr_invoices/', blank=True, null=True)
    corpus_contribution = models.DecimalField(max_digits=15, decimal_places=2)

    # Bank-transfer payment proof
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_PAYMENT')
    utr_number = models.CharField(max_length=50, blank=True, null=True)
    payment_proof = models.FileField(upload_to='jr_payment_proofs/', blank=True, null=True)

    # Snapshot of jewellery data used to create JRUnit after payment is verified
    pending_data = models.JSONField(null=True, blank=True)

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


class GoldAssessment(models.Model):
    """Standalone gold assessment certificate issued by jeweler before JR issuance"""
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('CONFIRMED', 'Confirmed')]
    PURITY_CHOICES = [('24K', '24K'), ('22K', '22K'), ('18K', '18K'), ('14K', '14K')]
    TEST_METHODS = [
        ('XRF', 'XRF Spectrometer'), ('ACID', 'Acid Test'),
        ('FIRE', 'Fire Assay'), ('DENSITY', 'Density Test'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jeweler = models.ForeignKey('core.JewelerProfile', on_delete=models.PROTECT, related_name='assessments')
    customer_email = models.EmailField()
    item_description = models.TextField()
    estimated_weight = models.DecimalField(max_digits=10, decimal_places=4)
    purity = models.CharField(max_length=4, choices=PURITY_CHOICES)
    test_method = models.CharField(max_length=10, choices=TEST_METHODS, default='XRF')
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    benchmark_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assessment_notes = models.TextField(blank=True)
    certificate_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'irg_jr_gold_assessment'
