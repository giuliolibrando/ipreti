from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LoginView, LogoutView
from rest_framework.routers import DefaultRouter

from reti_app.views import IndirizzoIPViewSet, health_check, VlanViewSet

# Configurazione API router
router = routers.DefaultRouter()
router.register(r'ips', IndirizzoIPViewSet)
router.register(r'vlans', VlanViewSet, basename='vlan')

# Configurazione Swagger/OpenAPI
schema_view = get_schema_view(
   openapi.Info(
      title="IP Reti API",
      default_version='v1',
      description="API per il sistema di gestione degli indirizzi IP",
      contact=openapi.Contact(email="admin@uniroma1.it"),
      license=openapi.License(name="Proprietario"),
   ),
   public=False,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Interfaccia utente principale
    path('', include('reti_app.urls')),
    
    # API REST
    path('api/', include(router.urls)),
    path('api/health/', health_check, name='api_health_check'),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # Documentazione API
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) 