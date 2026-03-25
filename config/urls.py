from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('apps.users.urls')),
    path('', include('apps.projects.urls')),
    path('', include('apps.payments.urls')),
    path('', include('apps.adminpanel.urls')),
]
