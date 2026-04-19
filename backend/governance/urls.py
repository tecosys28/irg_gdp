from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'proposals', views.ProposalViewSet, basename='proposal')
router.register(r'votes', views.VoteViewSet, basename='vote')
router.register(r'parameters', views.ParameterViewSet, basename='parameter')
router.register(r'actions', views.GovernanceActionViewSet, basename='action')

app_name = 'governance'
urlpatterns = [path('', include(router.urls))]
