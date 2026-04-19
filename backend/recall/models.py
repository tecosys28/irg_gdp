"""
Recall & DAC Models - Emergency Recall, Node Agent, Decentralized Autonomous Control
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group

Required per TGDP discussions - Previously missing from implementation.
"""
from django.db import models
from django.conf import settings
import uuid

class RecallOrder(models.Model):
    """Emergency recall of GDP/JR units"""
    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('APPROVED', 'Approved'),
        ('EXECUTING', 'Executing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    REASON_CHOICES = [
        ('FRAUD', 'Fraud Detection'),
        ('COMPLIANCE', 'Compliance Violation'),
        ('DISPUTE', 'Dispute Resolution'),
        ('SECURITY', 'Security Breach'),
        ('LEGAL', 'Legal Order'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()
    
    # Target
    target_units = models.JSONField(default=list)  # List of unit IDs
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, 
                                    related_name='recall_orders', null=True, blank=True)
    
    # Authority
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='initiated_recalls')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='approved_recalls')
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='INITIATED')
    
    # Blockchain
    recall_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'recall_order'
        ordering = ['-initiated_at']
    
    def __str__(self):
        return f"Recall-{str(self.id)[:8]} ({self.reason})"

class RecallAffectedUnit(models.Model):
    """Units affected by recall"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recall_order = models.ForeignKey(RecallOrder, on_delete=models.CASCADE, related_name='affected_units')
    
    unit_type = models.CharField(max_length=10)  # GDP, JR, GIC
    unit_id = models.UUIDField()
    original_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    original_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'recall_affected_unit'

class NodeAgent(models.Model):
    """Decentralized Node Agent for autonomous operations"""
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('MAINTENANCE', 'Maintenance'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    ROLE_CHOICES = [
        ('VALIDATOR', 'Validator Node'),
        ('ORACLE', 'Oracle Node'),
        ('RELAY', 'Relay Node'),
        ('ARCHIVE', 'Archive Node'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    
    # Network
    node_address = models.CharField(max_length=66, unique=True)
    endpoint_url = models.URLField()
    region = models.CharField(max_length=50)
    
    # Operator
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name='operated_nodes')
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='INACTIVE')
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    uptime_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Stake
    staked_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Performance
    blocks_validated = models.PositiveIntegerField(default=0)
    transactions_processed = models.PositiveIntegerField(default=0)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recall_node_agent'
    
    def __str__(self):
        return f"{self.name} ({self.role})"

class DACProposal(models.Model):
    """Decentralized Autonomous Control Proposal"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VOTING', 'Voting'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXECUTED', 'Executed'),
    ]
    
    TYPE_CHOICES = [
        ('RECALL', 'Emergency Recall'),
        ('PARAMETER', 'Parameter Change'),
        ('NODE', 'Node Management'),
        ('EMERGENCY', 'Emergency Action'),
        ('UPGRADE', 'System Upgrade'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    proposal_type = models.CharField(max_length=15, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # For recall proposals
    linked_recall = models.ForeignKey(RecallOrder, on_delete=models.SET_NULL, 
                                      null=True, blank=True, related_name='dac_proposals')
    
    # Voting
    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    votes_required = models.PositiveIntegerField(default=3)
    votes_received = models.PositiveIntegerField(default=0)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Blockchain
    blockchain_id = models.CharField(max_length=66, blank=True, null=True)
    execution_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'recall_dac_proposal'
        ordering = ['-created_at']

class DACVote(models.Model):
    """Vote on DAC proposal by node operators"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    proposal = models.ForeignKey(DACProposal, on_delete=models.CASCADE, related_name='votes')
    node = models.ForeignKey(NodeAgent, on_delete=models.CASCADE)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    approve = models.BooleanField()
    comment = models.TextField(blank=True)
    
    vote_tx_hash = models.CharField(max_length=66)
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recall_dac_vote'
        unique_together = ['proposal', 'node']

class EmergencyAction(models.Model):
    """Emergency actions taken by the system"""
    ACTION_CHOICES = [
        ('PAUSE', 'System Pause'),
        ('FREEZE', 'Account Freeze'),
        ('RECALL', 'Unit Recall'),
        ('RATE_LOCK', 'Rate Lock'),
        ('WITHDRAW_LOCK', 'Withdrawal Lock'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    action = models.CharField(max_length=15, choices=ACTION_CHOICES)
    reason = models.TextField()
    
    # Scope
    affected_scope = models.JSONField(default=dict)  # What was affected
    
    # Authority
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='emergency_actions')
    dac_proposal = models.ForeignKey(DACProposal, on_delete=models.SET_NULL, 
                                     null=True, blank=True)
    
    # Status
    active = models.BooleanField(default=True)
    reverted = models.BooleanField(default=False)
    reverted_at = models.DateTimeField(null=True, blank=True)
    reverted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='reverted_actions')
    
    # Blockchain
    action_tx_hash = models.CharField(max_length=66)
    revert_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    executed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recall_emergency_action'
        ordering = ['-executed_at']
