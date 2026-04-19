"""
Disputes Models - Dispute Resolution, Ombudsman Actions
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class Dispute(models.Model):
    """Dispute case"""
    STATUS_CHOICES = [('FILED','Filed'),('UNDER_REVIEW','Under Review'),('HEARING','Hearing'),('RESOLVED','Resolved'),('APPEALED','Appealed'),('CLOSED','Closed')]
    CATEGORY_CHOICES = [('BUYBACK','Buyback Issue'),('QUALITY','Quality Dispute'),('DELIVERY','Delivery Issue'),('PAYMENT','Payment Dispute'),('OTHER','Other')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_number = models.CharField(max_length=50, unique=True)
    
    filed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='disputes_filed')
    against = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='disputes_against')
    
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    evidence_files = models.JSONField(default=list)
    
    amount_in_dispute = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    assigned_ombudsman = models.ForeignKey('core.OmbudsmanProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_disputes')
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='FILED')
    priority = models.PositiveIntegerField(default=5)
    
    filed_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'disputes_case'
        ordering = ['-filed_at']

class Resolution(models.Model):
    """Dispute resolution record"""
    OUTCOME_CHOICES = [('FAVOR_FILER','In Favor of Filer'),('FAVOR_RESPONDENT','In Favor of Respondent'),('PARTIAL','Partial Resolution'),('WITHDRAWN','Withdrawn'),('SETTLED','Mutually Settled')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.OneToOneField(Dispute, on_delete=models.PROTECT, related_name='resolution')
    ombudsman = models.ForeignKey('core.OmbudsmanProfile', on_delete=models.PROTECT)
    
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    ruling = models.TextField()
    compensation_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    resolution_tx_hash = models.CharField(max_length=66)
    resolved_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'disputes_resolution'

class Compensation(models.Model):
    """Compensation payment record"""
    STATUS_CHOICES = [('ORDERED','Ordered'),('PAID','Paid'),('APPEALED','Appealed')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resolution = models.ForeignKey(Resolution, on_delete=models.PROTECT, related_name='compensations')
    
    from_party = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='compensations_paid')
    to_party = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='compensations_received')
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ORDERED')
    
    payment_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    ordered_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'disputes_compensation'

class AuditLog(models.Model):
    """System audit log"""
    ACTION_TYPES = [('CREATE','Create'),('UPDATE','Update'),('DELETE','Delete'),('ACCESS','Access'),('TRANSFER','Transfer')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    action = models.CharField(max_length=10, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50)
    changes = models.JSONField(default=dict)
    
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'disputes_audit_log'
        ordering = ['-timestamp']
