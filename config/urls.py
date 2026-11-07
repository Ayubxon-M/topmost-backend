from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

def privacy(request):
    """Maxfiylik siyosati. App Store va Google Play ilova sahifasida shu havolani so'raydi."""
    return render(request, 'privacy.html', {
        'updated': settings.PRIVACY_UPDATED,
        'contact': settings.PRIVACY_CONTACT,
    })


urlpatterns = [
    path('privacy/', privacy, name='privacy'),
    path('admin/', admin.site.urls),
    # API hujjati: /api/docs/ — brauzerda ochiladigan Swagger sahifasi
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include('catalog.urls')),
]

# E'lon rasmlari: /media/listings/... (settings.SERVE_MEDIA ga qarang)
if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
