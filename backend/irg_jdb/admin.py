from django.contrib import admin
from .models import Design, DesignOrder, RoyaltyPayment, Copyright, DesignLicense


@admin.register(Design)
class DesignAdmin(admin.ModelAdmin):
    list_display  = ['title', 'designer', 'category', 'status', 'views_count',
                     'orders_count', 'estimated_gold_weight', 'created_at']
    list_filter   = ['category', 'status']
    search_fields = ['title', 'designer__display_name', 'copyright_hash']
    readonly_fields = ['id', 'created_at', 'approved_at', 'copyright_registered_at']
    ordering      = ['-created_at']


@admin.register(DesignOrder)
class DesignOrderAdmin(admin.ModelAdmin):
    list_display  = ['design', 'jeweler', 'customer', 'quantity', 'agreed_price',
                     'status', 'placed_at']
    list_filter   = ['status']
    search_fields = ['design__title', 'jeweler__business_name', 'customer__email']
    readonly_fields = ['id', 'placed_at', 'completed_at']
    ordering      = ['-placed_at']


@admin.register(RoyaltyPayment)
class RoyaltyPaymentAdmin(admin.ModelAdmin):
    list_display  = ['designer', 'design_order', 'royalty_rate', 'amount', 'paid_at']
    search_fields = ['designer__display_name', 'payment_tx_hash']
    readonly_fields = ['id', 'paid_at']
    ordering      = ['-paid_at']


@admin.register(Copyright)
class CopyrightAdmin(admin.ModelAdmin):
    list_display  = ['copyright_number', 'design', 'designer', 'valid_from',
                     'valid_until', 'registered_at']
    search_fields = ['copyright_number', 'design__title', 'designer__display_name']
    readonly_fields = ['id', 'registered_at']


@admin.register(DesignLicense)
class DesignLicenseAdmin(admin.ModelAdmin):
    list_display  = ['design', 'licensed_to', 'license_fee', 'royalty_per_unit_sold',
                     'status', 'valid_until', 'created_at']
    list_filter   = ['status']
    search_fields = ['design__title', 'licensed_to__business_name']
    readonly_fields = ['id', 'created_at']
