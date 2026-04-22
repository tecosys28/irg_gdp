from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import (WalletActivation, NomineeRegistration, WalletDevice,
                     InactivityEvent, RecoveryCase, NomineeSignature, OwnershipTransferCase)


# ── WalletActivation actions ──────────────────────────────────────────────────

def _suspend_wallet(modeladmin, request, queryset):
    updated = queryset.exclude(state='SUSPENDED').update(state='SUSPENDED')
    modeladmin.message_user(request, f'{updated} wallet(s) suspended.', messages.WARNING)

def _unsuspend_wallet(modeladmin, request, queryset):
    updated = queryset.filter(state='SUSPENDED').update(state='ACTIVATED')
    modeladmin.message_user(request, f'{updated} wallet(s) reactivated.', messages.SUCCESS)

def _unlock_wallet(modeladmin, request, queryset):
    updated = 0
    for wallet in queryset.filter(state='LOCKED'):
        wallet.state = 'ACTIVATED'
        wallet.failed_password_attempts = 0
        wallet.locked_until = None
        wallet.save()
        updated += 1
    modeladmin.message_user(request, f'{updated} wallet(s) unlocked.', messages.SUCCESS)

_suspend_wallet.short_description   = 'Suspend selected wallets'
_unsuspend_wallet.short_description = 'Reactivate suspended wallets'
_unlock_wallet.short_description    = 'Unlock locked wallets (clear failed attempts)'


# ── RecoveryCase actions ──────────────────────────────────────────────────────

def _approve_recovery(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['FILED', 'NOTIFIED', 'AWAITING_SIGNATURES',
                                          'AWAITING_OMBUDSMAN']).update(status='APPROVED')
    modeladmin.message_user(request, f'{updated} recovery case(s) approved.', messages.SUCCESS)

def _reject_recovery(modeladmin, request, queryset):
    updated = queryset.exclude(status__in=['EXECUTED', 'REJECTED']).update(status='REJECTED')
    modeladmin.message_user(request, f'{updated} recovery case(s) rejected.', messages.WARNING)

def _execute_recovery(modeladmin, request, queryset):
    from services.blockchain import BlockchainService
    blockchain = BlockchainService()
    done = 0
    for case in queryset.filter(status='APPROVED'):
        try:
            tx_hash = blockchain.confirm_recovery_executed(
                case_id=str(case.id),
                order_hash=case.ombudsman_order_hash or '',
                execution_context='admin_execute',
            )
            case.execution_tx_hash = tx_hash
            case.status = 'EXECUTED'
            # Mark the original wallet as RECOVERED so it can no longer transact
            case.original_wallet.state = 'RECOVERED'
            case.original_wallet.save()
            case.save()
            done += 1
        except Exception as e:
            modeladmin.message_user(request, f'Case {case.id} failed: {e}', messages.ERROR)
    if done:
        modeladmin.message_user(request, f'{done} recovery case(s) executed.', messages.SUCCESS)

_approve_recovery.short_description = 'Approve selected recovery cases'
_reject_recovery.short_description  = 'Reject selected recovery cases'
_execute_recovery.short_description = 'Execute APPROVED recovery cases (marks wallet RECOVERED)'


# ── OwnershipTransferCase actions ─────────────────────────────────────────────

def _approve_transfer(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['FILED', 'AWAITING_OMBUDSMAN']).update(status='APPROVED')
    modeladmin.message_user(request, f'{updated} ownership transfer(s) approved.', messages.SUCCESS)

def _reject_transfer(modeladmin, request, queryset):
    updated = queryset.exclude(status__in=['EXECUTED', 'REJECTED']).update(status='REJECTED')
    modeladmin.message_user(request, f'{updated} ownership transfer(s) rejected.', messages.WARNING)

_approve_transfer.short_description = 'Approve selected ownership transfers'
_reject_transfer.short_description  = 'Reject selected ownership transfers'


# ── NomineeRegistration inline ────────────────────────────────────────────────

class NomineeInline(admin.TabularInline):
    model  = NomineeRegistration
    extra  = 0
    fields = ['name', 'relationship', 'email', 'share_percent', 'active']
    readonly_fields = ['created_at']
    show_change_link = True


class WalletDeviceInline(admin.TabularInline):
    model  = WalletDevice
    extra  = 0
    fields = ['device_label', 'platform', 'state', 'cooling_off_until', 'bound_at']
    readonly_fields = ['bound_at', 'activated_at']
    show_change_link = True


# ── Admin classes ─────────────────────────────────────────────────────────────

@admin.register(WalletActivation)
class WalletActivationAdmin(admin.ModelAdmin):
    list_display    = ['user', 'wallet_address', 'state', 'holder_type',
                       'seed_phrase_confirmed', 'created_at', 'activated_at']
    list_filter     = ['state', 'holder_type', 'seed_phrase_confirmed']
    search_fields   = ['user__email', 'wallet_address']
    readonly_fields = ['password_hash', 'password_salt', 'seed_phrase_hash',
                       'created_at', 'activated_at', 'last_state_change']
    inlines         = [NomineeInline, WalletDeviceInline]
    actions         = [_suspend_wallet, _unsuspend_wallet, _unlock_wallet]


@admin.register(NomineeRegistration)
class NomineeRegistrationAdmin(admin.ModelAdmin):
    list_display    = ['wallet', 'name', 'relationship', 'email', 'share_percent',
                       'active', 'created_at']
    list_filter     = ['relationship', 'active']
    search_fields   = ['name', 'email', 'mobile', 'wallet__user__email']
    readonly_fields = ['id_document_hash', 'created_at', 'updated_at', 'revoked_at']


@admin.register(WalletDevice)
class WalletDeviceAdmin(admin.ModelAdmin):
    list_display    = ['wallet', 'device_label', 'platform', 'state', 'bound_at', 'activated_at']
    list_filter     = ['platform', 'state']
    search_fields   = ['wallet__user__email', 'device_label']
    readonly_fields = ['device_id_hash', 'bind_tx_hash', 'revoke_tx_hash',
                       'bound_at', 'activated_at', 'retired_at']


@admin.register(InactivityEvent)
class InactivityEventAdmin(admin.ModelAdmin):
    list_display    = ['wallet', 'kind', 'occurred_at', 'detail']
    list_filter     = ['kind']
    search_fields   = ['wallet__user__email', 'detail']
    readonly_fields = ['occurred_at']
    ordering        = ['-occurred_at']


@admin.register(RecoveryCase)
class RecoveryCaseAdmin(admin.ModelAdmin):
    list_display    = ['original_wallet', 'path', 'status', 'claimant_user',
                       'claimant_wallet_address', 'created_at']
    list_filter     = ['path', 'status']
    search_fields   = ['original_wallet__user__email', 'claimant_user__email',
                       'claimant_wallet_address']
    readonly_fields = ['evidence_bundle_hash', 'ombudsman_order_hash',
                       'recovery_requested_tx_hash', 'execution_tx_hash',
                       'created_at', 'updated_at']
    ordering        = ['-created_at']
    actions         = [_approve_recovery, _reject_recovery, _execute_recovery]


@admin.register(NomineeSignature)
class NomineeSignatureAdmin(admin.ModelAdmin):
    list_display    = ['case', 'nominee', 'signed_at']
    search_fields   = ['nominee__email', 'case__id']
    readonly_fields = ['signature', 'signed_at']


@admin.register(OwnershipTransferCase)
class OwnershipTransferCaseAdmin(admin.ModelAdmin):
    list_display    = ['wallet', 'reason', 'status', 'outgoing_operator',
                       'incoming_operator', 'created_at']
    list_filter     = ['reason', 'status']
    search_fields   = ['wallet__user__email', 'outgoing_operator__email',
                       'incoming_operator__email']
    readonly_fields = ['evidence_bundle_hash', 'ombudsman_order_hash',
                       'transfer_requested_tx_hash', 'execution_tx_hash',
                       'created_at', 'updated_at']
    ordering        = ['-created_at']
    actions         = [_approve_transfer, _reject_transfer]
