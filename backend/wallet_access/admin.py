from django.contrib import admin
from .models import (WalletActivation, NomineeRegistration, WalletDevice,
                     InactivityEvent, RecoveryCase, NomineeSignature, OwnershipTransferCase)


@admin.register(WalletActivation)
class WalletActivationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'wallet_address', 'state', 'holder_type',
                     'seed_phrase_confirmed', 'created_at', 'activated_at']
    list_filter   = ['state', 'holder_type', 'seed_phrase_confirmed']
    search_fields = ['user__email', 'wallet_address']
    readonly_fields = ['password_hash', 'password_salt', 'seed_phrase_hash',
                       'created_at', 'activated_at', 'last_state_change']


@admin.register(NomineeRegistration)
class NomineeRegistrationAdmin(admin.ModelAdmin):
    list_display  = ['wallet', 'name', 'relationship', 'email', 'share_percent',
                     'active', 'created_at']
    list_filter   = ['relationship', 'active']
    search_fields = ['name', 'email', 'mobile', 'wallet__user__email']
    readonly_fields = ['id_document_hash', 'created_at', 'updated_at', 'revoked_at']


@admin.register(WalletDevice)
class WalletDeviceAdmin(admin.ModelAdmin):
    list_display  = ['wallet', 'device_label', 'platform', 'state', 'bound_at', 'activated_at']
    list_filter   = ['platform', 'state']
    search_fields = ['wallet__user__email', 'device_label']
    readonly_fields = ['device_id_hash', 'bind_tx_hash', 'revoke_tx_hash',
                       'bound_at', 'activated_at', 'retired_at']


@admin.register(InactivityEvent)
class InactivityEventAdmin(admin.ModelAdmin):
    list_display  = ['wallet', 'kind', 'occurred_at', 'detail']
    list_filter   = ['kind']
    search_fields = ['wallet__user__email', 'detail']
    readonly_fields = ['occurred_at']
    ordering      = ['-occurred_at']


@admin.register(RecoveryCase)
class RecoveryCaseAdmin(admin.ModelAdmin):
    list_display  = ['original_wallet', 'path', 'status', 'claimant_user',
                     'claimant_wallet_address', 'created_at']
    list_filter   = ['path', 'status']
    search_fields = ['original_wallet__user__email', 'claimant_user__email',
                     'claimant_wallet_address']
    readonly_fields = ['evidence_bundle_hash', 'ombudsman_order_hash',
                       'recovery_requested_tx_hash', 'execution_tx_hash',
                       'created_at', 'updated_at']
    ordering      = ['-created_at']


@admin.register(NomineeSignature)
class NomineeSignatureAdmin(admin.ModelAdmin):
    list_display  = ['case', 'nominee', 'signed_at']
    search_fields = ['nominee__email', 'case__id']
    readonly_fields = ['signature', 'signed_at']


@admin.register(OwnershipTransferCase)
class OwnershipTransferCaseAdmin(admin.ModelAdmin):
    list_display  = ['wallet', 'reason', 'status', 'outgoing_operator',
                     'incoming_operator', 'created_at']
    list_filter   = ['reason', 'status']
    search_fields = ['wallet__user__email', 'outgoing_operator__email',
                     'incoming_operator__email']
    readonly_fields = ['evidence_bundle_hash', 'ombudsman_order_hash',
                       'transfer_requested_tx_hash', 'execution_tx_hash',
                       'created_at', 'updated_at']
    ordering      = ['-created_at']
