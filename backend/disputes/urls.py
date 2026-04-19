from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'cases', views.DisputeViewSet, basename='dispute')
router.register(r'resolutions', views.ResolutionViewSet, basename='resolution')
router.register(r'compensations', views.CompensationViewSet, basename='compensation')
router.register(r'audit', views.AuditLogViewSet, basename='audit')

app_name = 'disputes'
urlpatterns = [path('', include(router.urls))]
