"""
Corpus Fund Models - Fund Management, Deposits, Investments
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.db import models
from django.conf import settings
import uuid

class CorpusFund(models.Model):
    """Main Corpus Fund entity"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jeweler = models.OneToOneField('core.JewelerProfile', on_delete=models.PROTECT, related_name='corpus_fund')
    
    total_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    physical_gold_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    other_investments_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    gold_grams_held = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    
    blockchain_address = models.CharField(max_length=66)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'corpus_fund'

class Deposit(models.Model):
    """Deposits into Corpus Fund"""
    DEPOSIT_TYPES = [('MINTING','Minting Contribution'),('JR_ISSUANCE','JR Issuance'),('VOLUNTARY','Voluntary'),('PENALTY','Penalty')]
    STATUS_CHOICES = [('PENDING','Pending'),('CONFIRMED','Confirmed'),('FAILED','Failed')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_fund = models.ForeignKey(CorpusFund, on_delete=models.PROTECT, related_name='deposits')
    depositor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    deposit_type = models.CharField(max_length=15, choices=DEPOSIT_TYPES)
    reference_id = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    deposit_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    deposited_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'corpus_deposit'

class Investment(models.Model):
    """Corpus Fund investments"""
    INVESTMENT_TYPES = [('PHYSICAL_GOLD','Physical Gold'),('GOLD_ETF','Gold ETF'),('GOVT_BONDS','Government Bonds'),('FIXED_DEPOSIT','Fixed Deposit')]
    STATUS_CHOICES = [('ACTIVE','Active'),('MATURED','Matured'),('LIQUIDATED','Liquidated')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_fund = models.ForeignKey(CorpusFund, on_delete=models.PROTECT, related_name='investments')
    
    investment_type = models.CharField(max_length=20, choices=INVESTMENT_TYPES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    current_value = models.DecimalField(max_digits=18, decimal_places=2)
    returns_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    
    invested_at = models.DateTimeField(auto_now_add=True)
    maturity_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'corpus_investment'

class Settlement(models.Model):
    """Corpus Fund settlements"""
    SETTLEMENT_TYPES = [('BUYBACK','Buyback Payment'),('BONUS','Bonus Distribution'),('WITHDRAWAL','Withdrawal')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_fund = models.ForeignKey(CorpusFund, on_delete=models.PROTECT, related_name='settlements')
    beneficiary = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    settlement_type = models.CharField(max_length=15, choices=SETTLEMENT_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reference_id = models.CharField(max_length=100)
    
    settlement_tx_hash = models.CharField(max_length=66)
    settled_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'corpus_settlement'


class CorpusBankAccount(models.Model):
    """Super Corpus Fund bank account details — editable by admin. Only one record can be active at a time."""
    account_name   = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    account_type   = models.CharField(max_length=50)
    bank_name      = models.CharField(max_length=200)
    branch         = models.CharField(max_length=200)
    city           = models.CharField(max_length=100)
    postal_code    = models.CharField(max_length=20)
    country        = models.CharField(max_length=100, default='INDIA')
    swift_code     = models.CharField(max_length=20, blank=True)
    ifsc_code      = models.CharField(max_length=20)
    is_active      = models.BooleanField(default=True)
    updated_at     = models.DateTimeField(auto_now=True)
    updated_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )

    class Meta:
        db_table = 'corpus_bank_account'

    def __str__(self):
        return f"{self.bank_name} — {self.account_number} ({'active' if self.is_active else 'inactive'})"

    def to_dict(self):
        return {
            'account_name':   self.account_name,
            'account_number': self.account_number,
            'account_type':   self.account_type,
            'bank_name':      self.bank_name,
            'branch':         self.branch,
            'city':           self.city,
            'postal_code':    self.postal_code,
            'country':        self.country,
            'swift_code':     self.swift_code,
            'ifsc_code':      self.ifsc_code,
        }


def get_active_bank_account():
    """Return the active CorpusBankAccount, falling back to settings.SUPER_CF_ACCOUNT."""
    account = CorpusBankAccount.objects.filter(is_active=True).order_by('-updated_at').first()
    if account:
        return account.to_dict()
    return getattr(settings, 'SUPER_CF_ACCOUNT', {})
