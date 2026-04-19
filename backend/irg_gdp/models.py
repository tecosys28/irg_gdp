"""
IRG_GDP Models - Main Product: Minting, Earmarking, Trading, Swap
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""

from django.db import models
from django.conf import settings
import uuid
from decimal import Decimal


class GDPUnit(models.Model):
    """
    IRG_GDP Unit - Represents blockchain registered right to swap
    at a value expressed in 24-carat gold at LBMA rate
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EARMARKED', 'Earmarked'),
        ('SWAPPED', 'Swapped'),
        ('TRANSFERRED', 'Transferred'),
        ('REDEEMED', 'Redeemed'),
        ('BURNED', 'Burned'),
    ]
    
    PURITY_CHOICES = [
        ('24K', '24 Karat'),
        ('22K', '22 Karat'),
        ('18K', '18 Karat'),
        ('14K', '14 Karat'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='gdp_units')
    
    # Gold backing
    gold_grams = models.DecimalField(max_digits=10, decimal_places=4)
    purity = models.CharField(max_length=5, choices=PURITY_CHOICES)
    pure_gold_equivalent = models.DecimalField(max_digits=10, decimal_places=4)
    
    # Benchmark value at minting
    benchmark_rate_at_mint = models.DecimalField(max_digits=12, decimal_places=2)  # INR per gram
    benchmark_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Unit details
    saleable_units = models.PositiveIntegerField()
    reserve_units = models.PositiveIntegerField()
    total_units = models.PositiveIntegerField()
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Source tracking
    source_jeweler = models.ForeignKey(
        'core.JewelerProfile', on_delete=models.PROTECT, 
        related_name='certified_units', null=True, blank=True
    )
    minting_record = models.ForeignKey(
        'MintingRecord', on_delete=models.PROTECT, 
        related_name='units', null=True, blank=True
    )
    
    # Blockchain
    blockchain_id = models.CharField(max_length=66, unique=True)
    minting_tx_hash = models.CharField(max_length=66)
    
    # Timestamps
    minted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'irg_gdp_unit'
        ordering = ['-minted_at']
    
    def __str__(self):
        return f"GDP-{str(self.id)[:8]} ({self.total_units} units)"
    
    def get_current_value(self, current_rate):
        """Calculate current value based on current LBMA rate"""
        return self.pure_gold_equivalent * Decimal(str(current_rate))


class MintingRecord(models.Model):
    """
    Record of GDP minting process with 5-point checklist
    """
    
    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('CHECKLIST_PENDING', 'Checklist Pending'),
        ('VERIFIED', 'Verified'),
        ('MINTING', 'Minting in Progress'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='minting_records')
    
    # Gold details
    gold_grams = models.DecimalField(max_digits=10, decimal_places=4)
    purity = models.CharField(max_length=5)
    pure_gold_equivalent = models.DecimalField(max_digits=10, decimal_places=4)
    
    # Invoice/Proof
    invoice_hash = models.CharField(max_length=66)
    invoice_file = models.FileField(upload_to='minting_invoices/', null=True, blank=True)
    
    # 5-Point Checklist
    invoice_verified = models.BooleanField(default=False)
    jeweler_certified = models.BooleanField(default=False)
    nw_certified = models.BooleanField(default=False)  # Net Worth Certificate
    within_cap = models.BooleanField(default=False)  # Within 500g cap
    undertaking_signed = models.BooleanField(default=False)
    
    # Certifiers
    certifying_jeweler = models.ForeignKey(
        'core.JewelerProfile', on_delete=models.PROTECT, 
        related_name='minting_certifications', null=True, blank=True
    )
    certifying_ca = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='nw_certifications', null=True, blank=True
    )
    
    # Output
    units_to_mint = models.PositiveIntegerField(default=0)
    saleable_units = models.PositiveIntegerField(default=0)
    reserve_units = models.PositiveIntegerField(default=0)
    earmarking_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    corpus_contribution = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INITIATED')
    rejection_reason = models.TextField(blank=True)
    
    # Blockchain
    transaction_hash = models.CharField(max_length=66, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'irg_gdp_minting_record'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Mint-{str(self.id)[:8]} ({self.gold_grams}g)"
    
    def is_checklist_complete(self):
        return all([
            self.invoice_verified,
            self.jeweler_certified,
            self.nw_certified,
            self.within_cap,
            self.undertaking_signed
        ])
    
    def calculate_units(self):
        """Calculate units based on config parameters"""
        config = settings.IRG_GDP_CONFIG
        purity_factor = {
            '24K': config['PURITY_24K'],
            '22K': config['PURITY_22K'],
            '18K': config['PURITY_18K'],
            '14K': config['PURITY_14K'],
        }.get(self.purity, 1.0)
        
        pure_gold = float(self.gold_grams) * purity_factor
        self.pure_gold_equivalent = Decimal(str(pure_gold))
        
        self.saleable_units = int(pure_gold * config['SALEABLE_PER_GRAM'])
        self.reserve_units = int(pure_gold * config['RESERVE_PER_GRAM'])
        self.units_to_mint = self.saleable_units + self.reserve_units
        
        return self.units_to_mint


class EarmarkingRecord(models.Model):
    """Record of earmarked GDP units"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('RELEASED', 'Released'),
        ('FORFEITED', 'Forfeited'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='earmarking_records')
    gdp_unit = models.ForeignKey(GDPUnit, on_delete=models.PROTECT, related_name='earmarking_records')
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    
    earmarked_at = models.DateTimeField(auto_now_add=True)
    release_date = models.DateField()
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Blockchain
    earmark_tx_hash = models.CharField(max_length=66)
    release_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    class Meta:
        db_table = 'irg_gdp_earmarking'
        ordering = ['-earmarked_at']
    
    def __str__(self):
        return f"Earmark-{str(self.id)[:8]} (₹{self.amount})"


class BonusAllocation(models.Model):
    """Bonus allocation from Corpus Fund surplus"""
    
    SOURCE_CHOICES = [
        ('CORPUS_SURPLUS', 'Corpus Fund Surplus'),
        ('TRADING_FEE', 'Trading Fee Share'),
        ('REFERRAL', 'Referral Bonus'),
    ]
    
    STATUS_CHOICES = [
        ('CALCULATED', 'Calculated'),
        ('APPROVED', 'Approved'),
        ('DISTRIBUTED', 'Distributed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bonus_allocations')
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    period = models.CharField(max_length=20)  # e.g., "2026-Q1"
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='CALCULATED')
    
    allocated_at = models.DateTimeField(auto_now_add=True)
    distributed_at = models.DateTimeField(null=True, blank=True)
    
    # Blockchain
    distribution_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    class Meta:
        db_table = 'irg_gdp_bonus'
        ordering = ['-allocated_at']
    
    def __str__(self):
        return f"Bonus-{str(self.id)[:8]} (₹{self.amount})"


class SwapRecord(models.Model):
    """Record of GDP swaps to FTRs"""
    
    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='swap_records')
    
    # Source
    gdp_units_swapped = models.PositiveIntegerField()
    gdp_value_at_swap = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Target FTR
    ftr_category = models.CharField(max_length=50)
    ftr_units_received = models.PositiveIntegerField()
    ftr_benchmark_rate = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='INITIATED')
    
    # Blockchain
    swap_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'irg_gdp_swap'
        ordering = ['-initiated_at']
    
    def __str__(self):
        return f"Swap-{str(self.id)[:8]} ({self.gdp_units_swapped} GDP → {self.ftr_category})"


class TradeRecord(models.Model):
    """Record of GDP trading (buy/sell)"""
    
    TRADE_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('MATCHED', 'Matched'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    trade_type = models.CharField(max_length=5, choices=TRADE_TYPES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='trade_records')
    counterparty = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, 
        related_name='counterparty_trades', null=True, blank=True
    )
    
    units = models.PositiveIntegerField()
    price_per_unit = models.DecimalField(max_digits=12, decimal_places=2)
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Blockchain
    trade_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'irg_gdp_trade'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.trade_type}-{str(self.id)[:8]} ({self.units} units)"


class TransferRecord(models.Model):
    """Record of GDP unit transfers (gift/sponsor)"""
    
    TRANSFER_TYPES = [
        ('GIFT', 'Gift'),
        ('SPONSOR', 'Sponsorship'),
        ('INHERITANCE', 'Inheritance'),
        ('SALE', 'Private Sale'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, 
        related_name='transfers_sent'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, 
        related_name='transfers_received'
    )
    
    gdp_unit = models.ForeignKey(GDPUnit, on_delete=models.PROTECT, related_name='transfers')
    transfer_type = models.CharField(max_length=15, choices=TRANSFER_TYPES)
    
    message = models.TextField(blank=True)
    
    # Blockchain
    transfer_tx_hash = models.CharField(max_length=66)
    
    transferred_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'irg_gdp_transfer'
        ordering = ['-transferred_at']
    
    def __str__(self):
        return f"Transfer-{str(self.id)[:8]} ({self.from_user} → {self.to_user})"
