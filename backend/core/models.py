"""
IRG_GDP Core Models - User, KYC, Participants, Multi-Role Management
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
import uuid


class User(AbstractUser):
    """Extended User model with multi-role support"""
<<<<<<< HEAD

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True, db_index=True)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, blank=True, validators=[
=======
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, unique=True, validators=[
>>>>>>> 6f5e39f (changhes05)
        RegexValidator(r'^\+?[0-9]{10,14}$', 'Enter a valid mobile number')
    ])
    
    # KYC Status
    KYC_TIERS = [
        ('NONE', 'Not Verified'),
        ('BASIC', 'Basic KYC'),
        ('ENHANCED', 'Enhanced KYC'),
        ('FULL', 'Full KYC'),
    ]
    kyc_tier = models.CharField(max_length=10, choices=KYC_TIERS, default='NONE')
    aadhaar_verified = models.BooleanField(default=False)
    pan_verified = models.BooleanField(default=False)
    bank_verified = models.BooleanField(default=False)
    
    # Profile
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Blockchain
    blockchain_address = models.CharField(max_length=66, blank=True, null=True)
    
    USERNAME_FIELD = 'email'
<<<<<<< HEAD
    REQUIRED_FIELDS = ['username']
=======
    REQUIRED_FIELDS = ['username', 'mobile']
>>>>>>> 6f5e39f (changhes05)
    
    class Meta:
        db_table = 'core_user'
    
    def __str__(self):
        return f"{self.email} ({self.get_full_name()})"


class UserRole(models.Model):
    """
    Multi-role support with constraint enforcement
    Based on User Multi-Role Constraint Matrix
    """
    
    ROLE_CHOICES = [
        ('JEWELER', 'Jeweler'),
        ('HOUSEHOLD', 'Household (Earmarking)'),
        ('INVESTOR', 'IRG_GDP/FTR Buyer'),
        ('RETURNEE', 'Jewelry Returnee'),
        ('DESIGNER', 'Jewelry Designer'),
        ('OMBUDSMAN', 'Ombudsman'),
        ('CONSULTANT', 'Consultant'),
        ('MARKETMAKER', 'Market Maker'),
        ('LICENSEE', 'Licensee'),
        ('MINTER', 'FTR Minter'),
        ('TRUSTEE', 'Trustee Banker'),
        ('ADMIN', 'Administrator'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('REVOKED', 'Revoked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_roles')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_user_role'
        unique_together = ['user', 'role']
    
    def __str__(self):
        return f"{self.user.email} - {self.get_role_display()}"
    
    @staticmethod
    def get_role_constraints():
        """
        Returns the role compatibility matrix
        True = Compatible, False = Incompatible
        """
        return {
            'JEWELER': {'HOUSEHOLD': False, 'INVESTOR': True, 'RETURNEE': False, 'DESIGNER': False, 
                       'OMBUDSMAN': False, 'CONSULTANT': False, 'MARKETMAKER': True, 'LICENSEE': False, 
                       'MINTER': False, 'TRUSTEE': False},
            'HOUSEHOLD': {'JEWELER': False, 'INVESTOR': True, 'RETURNEE': True, 'DESIGNER': True,
                         'OMBUDSMAN': False, 'CONSULTANT': False, 'MARKETMAKER': True, 'LICENSEE': True,
                         'MINTER': True, 'TRUSTEE': True},
            'INVESTOR': {'JEWELER': False, 'HOUSEHOLD': True, 'RETURNEE': True, 'DESIGNER': True,
                        'OMBUDSMAN': True, 'CONSULTANT': True, 'MARKETMAKER': True, 'LICENSEE': True,
                        'MINTER': True, 'TRUSTEE': True},
            'RETURNEE': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'DESIGNER': True,
                        'OMBUDSMAN': False, 'CONSULTANT': True, 'MARKETMAKER': True, 'LICENSEE': True,
                        'MINTER': True, 'TRUSTEE': True},
            'DESIGNER': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'RETURNEE': True,
                        'OMBUDSMAN': False, 'CONSULTANT': False, 'MARKETMAKER': True, 'LICENSEE': True,
                        'MINTER': True, 'TRUSTEE': False},
            'OMBUDSMAN': {'JEWELER': False, 'HOUSEHOLD': False, 'INVESTOR': True, 'RETURNEE': False,
                         'DESIGNER': False, 'CONSULTANT': False, 'MARKETMAKER': False, 'LICENSEE': False,
                         'MINTER': False, 'TRUSTEE': False},
            'CONSULTANT': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'RETURNEE': True,
                          'DESIGNER': False, 'OMBUDSMAN': False, 'MARKETMAKER': False, 'LICENSEE': False,
                          'MINTER': False, 'TRUSTEE': False},
            'MARKETMAKER': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'RETURNEE': True,
                           'DESIGNER': True, 'OMBUDSMAN': False, 'CONSULTANT': False, 'LICENSEE': True,
                           'MINTER': False, 'TRUSTEE': False},
            'LICENSEE': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'RETURNEE': False,
                        'DESIGNER': False, 'OMBUDSMAN': False, 'CONSULTANT': False, 'MARKETMAKER': True,
                        'MINTER': False, 'TRUSTEE': False},
            'MINTER': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'RETURNEE': True,
                      'DESIGNER': False, 'OMBUDSMAN': False, 'CONSULTANT': False, 'MARKETMAKER': False,
                      'LICENSEE': False, 'TRUSTEE': False},
            'TRUSTEE': {'JEWELER': False, 'HOUSEHOLD': True, 'INVESTOR': True, 'RETURNEE': True,
                       'DESIGNER': False, 'OMBUDSMAN': False, 'CONSULTANT': False, 'MARKETMAKER': False,
                       'LICENSEE': False, 'MINTER': False},
        }
    
    def is_compatible_with(self, other_role):
        """Check if this role is compatible with another role"""
        constraints = self.get_role_constraints()
        if self.role not in constraints:
            return True
        return constraints[self.role].get(other_role, True)


class KYCDocument(models.Model):
    """KYC Document storage and verification"""
    
    DOC_TYPES = [
        ('AADHAAR', 'Aadhaar Card'),
        ('PAN', 'PAN Card'),
        ('PASSPORT', 'Passport'),
        ('VOTER_ID', 'Voter ID'),
        ('DRIVING_LICENSE', 'Driving License'),
        ('BANK_STATEMENT', 'Bank Statement'),
        ('GST_CERT', 'GST Certificate'),
        ('JEWELER_LICENSE', 'Jeweler License'),
        ('COMPANY_REG', 'Company Registration'),
        ('ADDRESS_PROOF', 'Address Proof'),
    ]
    
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('UNDER_REVIEW', 'Under Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_documents')
    document_type = models.CharField(max_length=20, choices=DOC_TYPES)
    document_number = models.CharField(max_length=50)
    document_file = models.FileField(upload_to='kyc_documents/', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_documents')
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Blockchain hash for verification
    blockchain_hash = models.CharField(max_length=66, blank=True, null=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_kyc_document'
    
    def __str__(self):
        return f"{self.user.email} - {self.get_document_type_display()}"


class JewelerProfile(models.Model):
    """Extended profile for Jeweler role"""
    
    TIER_CHOICES = [
        ('BRONZE', 'Bronze'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinum'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='jeweler_profile')
    
    business_name = models.CharField(max_length=200)
    license_number = models.CharField(max_length=50, unique=True)
    gst_number = models.CharField(max_length=20)
    pan_number = models.CharField(max_length=10)
    
    business_address = models.TextField()
    years_in_business = models.PositiveIntegerField(default=0)
    
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='BRONZE')
    corpus_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Blockchain
    blockchain_address = models.CharField(max_length=66, blank=True, null=True)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_jeweler_profile'
    
    def __str__(self):
        return self.business_name


class DesignerProfile(models.Model):
    """Extended profile for Designer role"""
    
    TIER_CHOICES = [
        ('EMERGING', 'Emerging'),
        ('ESTABLISHED', 'Established'),
        ('MASTER', 'Master'),
    ]
    
    QUALIFICATION_CHOICES = [
        ('GIA', 'GIA Certified'),
        ('NIFT', 'NIFT Graduate'),
        ('SELF', 'Self-taught'),
        ('OTHER', 'Other Institute'),
    ]
    
    SPECIALIZATION_CHOICES = [
        ('GOLD', 'Gold Jewelry'),
        ('DIAMOND', 'Diamond Jewelry'),
        ('SILVER', 'Silver Jewelry'),
        ('KUNDAN', 'Kundan/Polki'),
        ('CONTEMPORARY', 'Contemporary'),
        ('TRADITIONAL', 'Traditional'),
        ('ALL', 'All Categories'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='designer_profile')
    
    display_name = models.CharField(max_length=100)
    portfolio_url = models.URLField(blank=True)
    qualification = models.CharField(max_length=10, choices=QUALIFICATION_CHOICES)
    experience_years = models.PositiveIntegerField(default=0)
    specialization = models.CharField(max_length=20, choices=SPECIALIZATION_CHOICES)
    
    # References (required if no formal degree)
    reference_jeweler_1 = models.CharField(max_length=200, blank=True)
    reference_jeweler_2 = models.CharField(max_length=200, blank=True)
    
    tier = models.CharField(max_length=15, choices=TIER_CHOICES, default='EMERGING')
    total_designs = models.PositiveIntegerField(default=0)
    total_orders = models.PositiveIntegerField(default=0)
    royalties_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Copyright count
    copyright_count = models.PositiveIntegerField(default=0)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_designer_profile'
    
    def __str__(self):
        return self.display_name
    
    def get_royalty_rate(self):
        """Get royalty rate based on tier"""
        rates = {
            'EMERGING': 2,
            'ESTABLISHED': 3,
            'MASTER': 5,
        }
        return rates.get(self.tier, 2)


class LicenseeProfile(models.Model):
    """Extended profile for Licensee role"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='licensee_profile')
    
    entity_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, unique=True)
    territory = models.CharField(max_length=200)
    investment_capacity = models.DecimalField(max_digits=15, decimal_places=2)
    industry_experience = models.TextField()
    
    license_valid_from = models.DateField(null=True, blank=True)
    license_valid_until = models.DateField(null=True, blank=True)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_licensee_profile'
    
    def __str__(self):
        return f"{self.entity_name} ({self.territory})"


class OmbudsmanProfile(models.Model):
    """Extended profile for Ombudsman role"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ombudsman_profile')
    
    qualification = models.CharField(max_length=200)
    bar_council_registration = models.CharField(max_length=50, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    professional_references = models.TextField()
    
    cases_resolved = models.PositiveIntegerField(default=0)
    avg_resolution_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_ombudsman_profile'
    
    def __str__(self):
        return f"Ombudsman: {self.user.get_full_name()}"


class MarketMakerProfile(models.Model):
    """Extended profile for Market Maker role"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='marketmaker_profile')
    
    entity_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50)
    available_capital = models.DecimalField(max_digits=15, decimal_places=2)
    trading_experience_years = models.PositiveIntegerField(default=0)
    
    total_volume = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    current_positions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_marketmaker_profile'
    
    def __str__(self):
        return self.entity_name


class TrusteeBankerProfile(models.Model):
    """Extended profile for Trustee Banker role"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='trustee_profile')
    
    bank_name = models.CharField(max_length=200)
    banking_license = models.CharField(max_length=50)
    designation = models.CharField(max_length=100)
    branch_details = models.CharField(max_length=200)
    
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_trustee_profile'
    
    def __str__(self):
        return f"{self.bank_name} - {self.designation}"
