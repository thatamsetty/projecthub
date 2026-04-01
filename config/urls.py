from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('apps.users.urls')),
    path('', include('apps.projects.urls')),
    path('', include('apps.payments.urls')),
    path('', include('apps.adminpanel.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
