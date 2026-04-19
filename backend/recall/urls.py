from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'orders', views.RecallOrderViewSet, basename='recall-order')
router.register(r'nodes', views.NodeAgentViewSet, basename='node-agent')
router.register(r'dac', views.DACProposalViewSet, basename='dac-proposal')
router.register(r'emergency', views.EmergencyActionViewSet, basename='emergency')

app_name = 'recall'
urlpatterns = [path('', include(router.urls))]
