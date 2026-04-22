from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'designs', views.DesignViewSet, basename='design')
router.register(r'orders', views.DesignOrderViewSet, basename='design-order')
router.register(r'royalties', views.RoyaltyPaymentViewSet, basename='royalty')
router.register(r'licenses', views.DesignLicenseViewSet, basename='design-license')

app_name = 'irg_jdb'
urlpatterns = [path('', include(router.urls))]
