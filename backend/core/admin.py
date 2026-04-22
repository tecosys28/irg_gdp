"""
IRG_GDP Django Admin Configuration
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

class IRGAdminSite(admin.AdminSite):
    site_header = "IRG_GDP Administration"
    site_title = "IRG_GDP Admin"
    index_title = "System Management"

admin_site = IRGAdminSite(name='irg_admin')

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'get_full_name', 'mobile', 'city', 'kyc_tier', 'is_active', 'created_at']
    list_filter = ['kyc_tier', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name', 'mobile', 'firebase_uid']
    ordering = ['-created_at']
    fieldsets = UserAdmin.fieldsets + (
        ('IRG Profile', {'fields': ('firebase_uid', 'mobile', 'city', 'state', 'pincode',
                                    'kyc_tier', 'aadhaar_verified', 'pan_verified',
                                    'bank_verified', 'blockchain_address')}),
    )

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'status', 'created_at', 'approved_at']
    list_filter = ['role', 'status']
    search_fields = ['user__email']

@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'document_type', 'status', 'uploaded_at']
    list_filter = ['document_type', 'status']

@admin.register(JewelerProfile)
class JewelerProfileAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'license_number', 'tier', 'corpus_balance', 'rating']
    list_filter = ['tier']
    search_fields = ['business_name', 'license_number']

@admin.register(DesignerProfile)
class DesignerProfileAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'tier', 'total_designs', 'royalties_earned']
    list_filter = ['tier', 'specialization']

@admin.register(LicenseeProfile)
class LicenseeProfileAdmin(admin.ModelAdmin):
    list_display = ['entity_name', 'territory', 'license_valid_until']

@admin.register(OmbudsmanProfile)
class OmbudsmanProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'cases_resolved', 'avg_resolution_days']

@admin.register(MarketMakerProfile)
class MarketMakerProfileAdmin(admin.ModelAdmin):
    list_display = ['entity_name', 'available_capital', 'total_volume']

@admin.register(TrusteeBankerProfile)
class TrusteeBankerProfileAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'designation', 'branch_details']
