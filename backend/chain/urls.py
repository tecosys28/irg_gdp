from django.urls import path

from . import views


def _licence_status(request):
    from django.http import JsonResponse
    from .licence_guard import current_licence_info
    return JsonResponse(current_licence_info())


urlpatterns = [
    path('audit/', views.audit_sink, name='chain-audit-sink'),
    path('licence/status', _licence_status, name='chain-licence-status'),
]
