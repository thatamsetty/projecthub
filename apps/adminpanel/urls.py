from django.urls import path

from apps.adminpanel.views import (
    admin_dashboard_view,
    admin_login_view,
    admin_payments_view,
    admin_project_edit_view,
    admin_projects_view,
    admin_user_project_edit_view,
    admin_users_view,
)

urlpatterns = [
    path('admin-auth/login/', admin_login_view, name='admin_login'),
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin/projects/', admin_projects_view, name='admin_projects'),
    path('admin/projects/<int:project_id>/edit/', admin_project_edit_view, name='admin_project_edit'),
    path('admin/users/', admin_users_view, name='admin_users'),
    path('admin/users/projects/<int:user_project_id>/edit/', admin_user_project_edit_view, name='admin_user_project_edit'),
    path('admin/payments/', admin_payments_view, name='admin_payments'),
]
