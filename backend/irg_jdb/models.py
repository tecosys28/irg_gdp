"""
irg_jdb Models - Designer Bank for Creators and Jewelers
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class Design(models.Model):
    """Jewelry Design with blockchain-registered copyright"""
    STATUS_CHOICES = [('DRAFT','Draft'),('SUBMITTED','Submitted'),('APPROVED','Approved'),('REJECTED','Rejected'),('ARCHIVED','Archived')]
    CATEGORY_CHOICES = [('RING','Ring'),('NECKLACE','Necklace'),('BRACELET','Bracelet'),('EARRING','Earring'),('PENDANT','Pendant'),('BANGLE','Bangle'),('OTHER','Other')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    designer = models.ForeignKey('core.DesignerProfile', on_delete=models.PROTECT, related_name='designs')
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    design_file = models.FileField(upload_to='designs/')
    thumbnail = models.ImageField(upload_to='design_thumbnails/')
    
    estimated_gold_weight = models.DecimalField(max_digits=10, decimal_places=4)
    estimated_making_charges = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    views_count = models.PositiveIntegerField(default=0)
    orders_count = models.PositiveIntegerField(default=0)
    
    copyright_hash = models.CharField(max_length=66, blank=True, null=True)
    copyright_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    copyright_registered_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'irg_jdb_design'

class DesignOrder(models.Model):
    """Order for a design from jeweler"""
    STATUS_CHOICES = [('PLACED','Placed'),('ACCEPTED','Accepted'),('IN_PROGRESS','In Progress'),('COMPLETED','Completed'),('CANCELLED','Cancelled')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    design = models.ForeignKey(Design, on_delete=models.PROTECT, related_name='orders')
    jeweler = models.ForeignKey('core.JewelerProfile', on_delete=models.PROTECT, related_name='design_orders')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    
    quantity = models.PositiveIntegerField(default=1)
    customization_notes = models.TextField(blank=True)
    agreed_price = models.DecimalField(max_digits=15, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PLACED')
    
    order_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'irg_jdb_order'

class RoyaltyPayment(models.Model):
    """Royalty payment to designer"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    designer = models.ForeignKey('core.DesignerProfile', on_delete=models.PROTECT, related_name='royalty_payments')
    design_order = models.ForeignKey(DesignOrder, on_delete=models.PROTECT, related_name='royalty_payments')
    
    royalty_rate = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    payment_tx_hash = models.CharField(max_length=66)
    paid_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'irg_jdb_royalty'

class Copyright(models.Model):
    """Blockchain-registered copyright for designs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    design = models.OneToOneField(Design, on_delete=models.PROTECT, related_name='copyright_record')
    designer = models.ForeignKey('core.DesignerProfile', on_delete=models.PROTECT)
    
    copyright_number = models.CharField(max_length=50, unique=True)
    design_hash = models.CharField(max_length=66)
    registration_tx_hash = models.CharField(max_length=66)
    
    valid_from = models.DateField()
    valid_until = models.DateField()
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'irg_jdb_copyright'
