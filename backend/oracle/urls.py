from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'lbma', views.LBMARateViewSet, basename='lbma')
router.register(r'benchmark', views.BenchmarkValueViewSet, basename='benchmark')
router.register(r'nodes', views.OracleNodeViewSet, basename='oracle-node')

app_name = 'oracle'
urlpatterns = [path('', include(router.urls))]
