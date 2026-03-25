from django.urls import path

from apps.users.views import dashboard_view, home_redirect_view, login_view, logout_view, register_view, verify_otp_view

urlpatterns = [
    path('', home_redirect_view, name='home'),
    path('auth/login/', login_view, name='login'),
    path('auth/register/', register_view, name='register'),
    path('auth/verify-otp/', verify_otp_view, name='verify_otp'),
    path('auth/logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
]
