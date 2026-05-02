
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

from ninProject import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('ninUser.urls')),
    path('api/chat/', include('chat.urls')),

    
    # OpenAPI schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    # Swagger UI
    path(
        'api/docs/swagger/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui'
    ),

    # Redoc
    path(
        'api/docs/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc'
    ),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
