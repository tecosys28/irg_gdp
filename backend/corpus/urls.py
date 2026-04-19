from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'funds', views.CorpusFundViewSet, basename='corpus-fund')
router.register(r'deposits', views.DepositViewSet, basename='deposit')
router.register(r'settlements', views.SettlementViewSet, basename='settlement')
router.register(r'investments', views.InvestmentViewSet, basename='investment')

app_name = 'corpus'
urlpatterns = [path('', include(router.urls))]
