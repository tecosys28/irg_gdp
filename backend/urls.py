"""
IRG_GDP URL Configuration
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from django.contrib import admin
<<<<<<< HEAD
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def healthz(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('healthz', healthz, name='healthz'),
    path('healthz/', healthz),
    path('admin/', admin.site.urls),
=======
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', obtain_auth_token, name='api_token'),
>>>>>>> 6f5e39f (changhes05)
    path('api/v1/auth/', include('core.urls')),
    path('api/v1/gdp/', include('irg_gdp.urls')),
    path('api/v1/jr/', include('irg_jr.urls')),
    path('api/v1/jdb/', include('irg_jdb.urls')),
    path('api/v1/gic/', include('irg_gic.urls')),
    path('api/v1/oracle/', include('oracle.urls')),
    path('api/v1/corpus/', include('corpus.urls')),
    path('api/v1/governance/', include('governance.urls')),
    path('api/v1/disputes/', include('disputes.urls')),
    path('api/v1/recall/', include('recall.urls')),
    path('api/v1/chain/', include('chain.urls')),
    path('api/v1/wallet/', include('wallet_access.urls')),
    # IRG Payment Autonomy bridge — canonical corpus + super-corpus routing
    # that every GDP corpus/payment operation now flows through.
    path('api/paa/', include('payment_bridge.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
