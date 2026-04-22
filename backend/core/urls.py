from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'roles', views.UserRoleViewSet, basename='role')
router.register(r'kyc', views.KYCDocumentViewSet, basename='kyc')
router.register(r'jewelers', views.JewelerProfileViewSet, basename='jeweler')
router.register(r'designers', views.DesignerProfileViewSet, basename='designer')
router.register(r'consultants', views.ConsultantProfileViewSet, basename='consultant')
router.register(r'advertisers', views.AdvertiserProfileViewSet, basename='advertiser')
router.register(r'ads', views.AdvertisementViewSet, basename='advertisement')

app_name = 'core'
urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('', include(router.urls)),
]
