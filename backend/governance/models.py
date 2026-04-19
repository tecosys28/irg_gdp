"""
Governance Models - Proposals, Voting, Parameters
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class Proposal(models.Model):
    """Governance proposal"""
    STATUS_CHOICES = [('DRAFT','Draft'),('ACTIVE','Active Voting'),('PASSED','Passed'),('REJECTED','Rejected'),('EXECUTED','Executed')]
    CATEGORY_CHOICES = [('PARAMETER','Parameter Change'),('POLICY','Policy Change'),('UPGRADE','System Upgrade'),('OTHER','Other')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='proposals')
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES)
    
    voting_starts = models.DateTimeField()
    voting_ends = models.DateTimeField()
    
    votes_for = models.PositiveIntegerField(default=0)
    votes_against = models.PositiveIntegerField(default=0)
    quorum_required = models.PositiveIntegerField(default=100)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    
    blockchain_id = models.CharField(max_length=66, blank=True, null=True)
    execution_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'governance_proposal'

class Vote(models.Model):
    """Vote on a proposal"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(Proposal, on_delete=models.PROTECT, related_name='votes')
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    vote_for = models.BooleanField()
    voting_power = models.PositiveIntegerField(default=1)
    
    vote_tx_hash = models.CharField(max_length=66)
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'governance_vote'
        unique_together = ['proposal', 'voter']

class Parameter(models.Model):
    """System parameters managed by governance"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=200)
    value_type = models.CharField(max_length=20)
    description = models.TextField()
    
    last_updated = models.DateTimeField(auto_now=True)
    updated_by_proposal = models.ForeignKey(Proposal, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'governance_parameter'

class GovernanceAction(models.Model):
    """Executed governance actions audit log"""
    ACTION_TYPES = [('PARAM_CHANGE','Parameter Change'),('ROLE_GRANT','Role Grant'),('ROLE_REVOKE','Role Revoke'),('EMERGENCY','Emergency Action')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_type = models.CharField(max_length=15, choices=ACTION_TYPES)
    description = models.TextField()
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    proposal = models.ForeignKey(Proposal, on_delete=models.SET_NULL, null=True, blank=True)
    
    action_tx_hash = models.CharField(max_length=66)
    executed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'governance_action'
