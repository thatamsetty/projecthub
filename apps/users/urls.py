from django.urls import path

from apps.users.views import (
    dashboard_view,
    forgot_password_request_view,
    forgot_password_reset_view,
    forgot_password_verify_otp_view,
    home_redirect_view,
    login_view,
    logout_view,
    clear_all_notifications_view,
    mark_notification_read_view,
    register_view,
    verify_otp_view,
)

urlpatterns = [
    path('', home_redirect_view, name='home'),
    path('auth/login/', login_view, name='login'),
    path('auth/register/', register_view, name='register'),
    path('auth/verify-otp/', verify_otp_view, name='verify_otp'),
    path('auth/forgot-password/', forgot_password_request_view, name='forgot_password'),
    path('auth/forgot-password/verify-otp/', forgot_password_verify_otp_view, name='forgot_password_verify_otp'),
    path('auth/forgot-password/reset/', forgot_password_reset_view, name='forgot_password_reset'),
    path('auth/logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('notifications/<int:notification_id>/read/', mark_notification_read_view, name='mark_notification_read'),
    path('notifications/clear/', clear_all_notifications_view, name='clear_all_notifications'),
]
