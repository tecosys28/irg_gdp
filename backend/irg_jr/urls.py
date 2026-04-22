from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'units', views.JRUnitViewSet, basename='jr-unit')
router.register(r'issuance', views.IssuanceViewSet, basename='issuance')
router.register(r'buyback', views.BuybackViewSet, basename='buyback')
router.register(r'assessments', views.GoldAssessmentViewSet, basename='gold-assessment')

app_name = 'irg_jr'
urlpatterns = [path('', include(router.urls))]
