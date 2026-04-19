from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'units', views.GDPUnitViewSet, basename='gdp-unit')
router.register(r'minting', views.MintingViewSet, basename='minting')
router.register(r'swap', views.SwapViewSet, basename='swap')
router.register(r'trade', views.TradeViewSet, basename='trade')
router.register(r'transfer', views.TransferViewSet, basename='transfer')
router.register(r'earmarking', views.EarmarkingViewSet, basename='earmarking')
router.register(r'bonus', views.BonusAllocationViewSet, basename='bonus')

app_name = 'irg_gdp'
urlpatterns = [
    path('', include(router.urls)),
]
