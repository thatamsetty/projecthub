from django.urls import path

from apps.adminpanel.views import (
    admin_dashboard_view,
    admin_login_view,
    admin_payments_view,
    admin_payment_user_detail_view,
    admin_project_edit_view,
    admin_project_payment_detail_view,
    admin_project_payment_invoice_view,
    admin_projects_view,
    admin_user_project_edit_view,
    admin_users_view,
)
from apps.users.views import (
    forgot_password_request_view,
    forgot_password_reset_view,
    forgot_password_verify_otp_view,
)

urlpatterns = [
    path('admin-auth/login/', admin_login_view, name='admin_login'),
    path('admin-auth/forgot-password/', forgot_password_request_view, {'role': 'admin'}, name='admin_forgot_password'),
    path(
        'admin-auth/forgot-password/verify-otp/',
        forgot_password_verify_otp_view,
        {'role': 'admin'},
        name='admin_forgot_password_verify_otp',
    ),
    path(
        'admin-auth/forgot-password/reset/',
        forgot_password_reset_view,
        {'role': 'admin'},
        name='admin_forgot_password_reset',
    ),
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin/projects/', admin_projects_view, name='admin_projects'),
    path('admin/projects/<int:project_id>/edit/', admin_project_edit_view, name='admin_project_edit'),
    path('admin/users/', admin_users_view, name='admin_users'),
    path('admin/users/projects/<int:user_project_id>/edit/', admin_user_project_edit_view, name='admin_user_project_edit'),
    path('admin/payments/', admin_payments_view, name='admin_payments'),
    path('admin/payments/users/<int:user_id>/', admin_payment_user_detail_view, name='admin_payment_user_detail'),
    path('admin/payments/projects/<int:user_project_id>/', admin_project_payment_detail_view, name='admin_project_payment_detail'),
    path(
        'admin/payments/projects/<int:user_project_id>/invoice/',
        admin_project_payment_invoice_view,
        name='admin_project_payment_invoice',
    ),
]
