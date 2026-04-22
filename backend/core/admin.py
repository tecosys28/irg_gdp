"""
IRG_GDP Django Admin Configuration
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.contrib import messages
from .models import (User, UserRole, KYCDocument, JewelerProfile, DesignerProfile,
                     LicenseeProfile, OmbudsmanProfile, MarketMakerProfile,
                     TrusteeBankerProfile, ConsultantProfile, AdvertiserProfile, Advertisement)


# ── KYC Document inline on User ───────────────────────────────────────────────

class KYCDocumentInline(admin.TabularInline):
    model = KYCDocument
    fk_name = 'user'
    extra = 0
    fields = ['document_type', 'document_number', 'status', 'verified_at']
    readonly_fields = ['uploaded_at', 'verified_at']
    show_change_link = True


class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = 'user'
    extra = 0
    fields = ['role', 'status', 'approved_by', 'approved_at']
    readonly_fields = ['approved_by', 'approved_at', 'created_at']
    show_change_link = True


# ── User ──────────────────────────────────────────────────────────────────────

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ['email', 'get_full_name', 'mobile', 'city', 'kyc_tier', 'is_active', 'created_at']
    list_filter   = ['kyc_tier', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name', 'mobile', 'firebase_uid']
    ordering      = ['-created_at']
    inlines       = [UserRoleInline, KYCDocumentInline]
    fieldsets = UserAdmin.fieldsets + (
        ('IRG Profile', {'fields': (
            'firebase_uid', 'mobile', 'city', 'state', 'pincode',
            'kyc_tier', 'aadhaar_verified', 'pan_verified',
            'bank_verified', 'blockchain_address',
        )}),
    )


# ── UserRole ──────────────────────────────────────────────────────────────────

def _approve_roles(modeladmin, request, queryset):
    updated = queryset.filter(status='PENDING').update(
        status='ACTIVE',
        approved_by=request.user,
        approved_at=timezone.now(),
    )
    modeladmin.message_user(request, f'{updated} role(s) approved.', messages.SUCCESS)

def _suspend_roles(modeladmin, request, queryset):
    updated = queryset.exclude(status__in=['REVOKED']).update(status='SUSPENDED')
    modeladmin.message_user(request, f'{updated} role(s) suspended.', messages.WARNING)

def _revoke_roles(modeladmin, request, queryset):
    updated = queryset.exclude(status='REVOKED').update(status='REVOKED')
    modeladmin.message_user(request, f'{updated} role(s) revoked.', messages.WARNING)

_approve_roles.short_description = 'Approve selected roles'
_suspend_roles.short_description = 'Suspend selected roles'
_revoke_roles.short_description  = 'Revoke selected roles'


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display  = ['user', 'role', 'status', 'approved_by', 'approved_at', 'created_at']
    list_filter   = ['role', 'status']
    search_fields = ['user__email']
    readonly_fields = ['id', 'approved_by', 'approved_at', 'created_at', 'updated_at']
    actions       = [_approve_roles, _suspend_roles, _revoke_roles]

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data and obj.status == 'ACTIVE' and not obj.approved_by:
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)


# ── KYC Document ──────────────────────────────────────────────────────────────

def _verify_kyc(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['UPLOADED', 'UNDER_REVIEW']).update(
        status='VERIFIED',
        verified_by=request.user,
        verified_at=timezone.now(),
    )
    modeladmin.message_user(request, f'{updated} document(s) verified.', messages.SUCCESS)

def _reject_kyc(modeladmin, request, queryset):
    updated = queryset.exclude(status='VERIFIED').update(status='REJECTED')
    modeladmin.message_user(request, f'{updated} document(s) rejected.', messages.WARNING)

def _mark_under_review(modeladmin, request, queryset):
    updated = queryset.filter(status='UPLOADED').update(status='UNDER_REVIEW')
    modeladmin.message_user(request, f'{updated} document(s) marked under review.', messages.INFO)

_verify_kyc.short_description       = 'Verify selected KYC documents'
_reject_kyc.short_description       = 'Reject selected KYC documents'
_mark_under_review.short_description = 'Mark selected documents as Under Review'


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display    = ['user', 'document_type', 'document_number', 'status', 'verified_by', 'verified_at', 'uploaded_at']
    list_filter     = ['document_type', 'status']
    search_fields   = ['user__email', 'document_number']
    readonly_fields = ['id', 'uploaded_at', 'verified_by', 'verified_at']
    actions         = [_verify_kyc, _reject_kyc, _mark_under_review]

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data and obj.status == 'VERIFIED':
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
        super().save_model(request, obj, form, change)


# ── Profile admins ────────────────────────────────────────────────────────────

@admin.register(JewelerProfile)
class JewelerProfileAdmin(admin.ModelAdmin):
    list_display  = ['business_name', 'license_number', 'tier', 'corpus_balance', 'rating']
    list_filter   = ['tier']
    search_fields = ['business_name', 'license_number']

@admin.register(DesignerProfile)
class DesignerProfileAdmin(admin.ModelAdmin):
    list_display  = ['display_name', 'tier', 'total_designs', 'royalties_earned']
    list_filter   = ['tier', 'specialization']

@admin.register(LicenseeProfile)
class LicenseeProfileAdmin(admin.ModelAdmin):
    list_display  = ['entity_name', 'territory', 'license_valid_until']

@admin.register(OmbudsmanProfile)
class OmbudsmanProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'cases_resolved', 'avg_resolution_days']

@admin.register(MarketMakerProfile)
class MarketMakerProfileAdmin(admin.ModelAdmin):
    list_display  = ['entity_name', 'available_capital', 'total_volume']

@admin.register(TrusteeBankerProfile)
class TrusteeBankerProfileAdmin(admin.ModelAdmin):
    list_display  = ['bank_name', 'designation', 'branch_details']

@admin.register(ConsultantProfile)
class ConsultantProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'expertise', 'years_experience', 'rating']
    search_fields = ['user__email']

@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'company_name', 'registered_at']
    search_fields = ['user__email', 'company_name']


# ── Advertisement ─────────────────────────────────────────────────────────────

def _approve_ads(modeladmin, request, queryset):
    updated = queryset.filter(status='PENDING').update(status='ACTIVE')
    modeladmin.message_user(request, f'{updated} advertisement(s) approved.', messages.SUCCESS)

def _reject_ads(modeladmin, request, queryset):
    updated = queryset.filter(status='PENDING').update(status='REJECTED')
    modeladmin.message_user(request, f'{updated} advertisement(s) rejected.', messages.WARNING)

_approve_ads.short_description = 'Approve selected advertisements'
_reject_ads.short_description  = 'Reject selected advertisements'


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display  = ['title', 'advertiser', 'status', 'budget', 'created_at']
    list_filter   = ['status']
    search_fields = ['title', 'advertiser__company_name']
    readonly_fields = ['id', 'created_at']
    actions       = [_approve_ads, _reject_ads]
