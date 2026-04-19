"""
IRG PAA Bridge — URL conf

Mount under /api/paa/ in the root urls.py:

    path("api/paa/", include("payment_bridge.urls")),
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"corpus-funds", views.CorpusFundViewSet, basename="paa-cf")
router.register(r"transactions", views.PaaTransactionViewSet, basename="paa-tx")

app_name = "payment_bridge"
urlpatterns = [
    path("", include(router.urls)),
    path("budget/active/",    views.active_budget,     name="active-budget"),
    path("dashboard/",        views.dashboard_metrics, name="dashboard"),
    path("audit/",            views.audit_log,         name="audit-log"),
    path("meta/",             views.bridge_meta,       name="bridge-meta"),
    path("health/",           views.bridge_health,     name="bridge-health"),
    path("rpc/",              views.rpc,               name="bridge-rpc"),
]
