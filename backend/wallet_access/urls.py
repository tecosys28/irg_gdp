from django.urls import path

from . import views

urlpatterns = [
    # Info
    path('info/', views.wallet_info, name='wallet-info'),
    path('status-banner/', views.wallet_status_banner, name='wallet-status-banner'),

    # Activation & password
    path('activate/', views.activate, name='wallet-activate'),
    path('password/change/', views.change_password, name='wallet-password-change'),
    path('password/verify/', views.verify_password, name='wallet-password-verify'),

    # Nominees
    path('nominees/', views.list_nominees, name='wallet-nominees'),
    path('nominees/update/', views.update_nominees, name='wallet-nominees-update'),

    # Devices
    path('devices/', views.list_devices, name='wallet-devices'),
    path('devices/bind/', views.bind_device, name='wallet-device-bind'),
    path('devices/revoke/', views.revoke_device, name='wallet-device-revoke'),

    # Freeze
    path('freeze/', views.emergency_freeze, name='wallet-freeze'),

    # Inactivity (activity-based watchdog, replaces old liveness)
    path('liveness/confirm/', views.confirm_liveness, name='wallet-liveness-confirm'),
    path('liveness/history/', views.liveness_history, name='wallet-liveness-history'),

    # Recovery
    path('recovery/self/', views.recover_self, name='wallet-recover-self'),
    path('recovery/social/', views.recover_social, name='wallet-recover-social'),
    path('recovery/trustee/', views.recover_trustee, name='wallet-recover-trustee'),
    path('recovery/cancel/', views.cancel_recovery_view, name='wallet-recover-cancel'),
    path('recovery/cases/', views.list_recovery_cases, name='wallet-recovery-cases'),

    # Ownership transfer (legal-person wallets only)
    path('ownership/initiate/', views.initiate_ownership_transfer, name='wallet-ownership-initiate'),
    path('ownership/cancel/', views.cancel_ownership_transfer_view, name='wallet-ownership-cancel'),
    path('ownership/cases/', views.list_ownership_transfers, name='wallet-ownership-cases'),

    # Reports
    path('transactions/', views.transaction_history, name='wallet-transactions'),
    path('transactions/export.csv', views.transaction_history_csv, name='wallet-transactions-csv'),

    # Public — heir guide (no auth)
    path('heir-guide/', views.heir_guide, name='wallet-heir-guide'),
]
