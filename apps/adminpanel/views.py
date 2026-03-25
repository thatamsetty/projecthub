from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.adminpanel.decorators import staff_required
from apps.adminpanel.forms import AdminLoginForm
from apps.projects.forms import ProjectCatalogForm, UserProjectAdminForm
from apps.projects.models import ProjectCatalog, UserProject
from services.admin_service import AdminService
from services.user_service import UserAuthService


def admin_login_view(request):
    form = AdminLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = UserAuthService().login(request, form.cleaned_data['username'], form.cleaned_data['password'])
        if user and user.is_staff:
            return redirect('/admin-dashboard/')
        if user and not user.is_staff:
            logout(request)
        form.add_error(None, 'Staff access required.')
    return render(request, 'admin/login.html', {'form': form})


@staff_required
def admin_dashboard_view(request):
    context = AdminService().dashboard_summary()
    return render(request, 'admin/dashboard.html', context)


@staff_required
def admin_projects_view(request):
    form = ProjectCatalogForm(request.POST or None)
    context = AdminService().list_project_catalog_context()
    if request.method == 'POST' and form.is_valid():
        try:
            AdminService().create_catalog_item(form.cleaned_data)
            return redirect('/admin/projects/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    context['form'] = form
    return render(request, 'admin/projects.html', context)


@staff_required
def admin_project_edit_view(request, project_id):
    project = get_object_or_404(ProjectCatalog, pk=project_id)
    form = ProjectCatalogForm(request.POST or None, instance=project)
    if request.method == 'POST' and form.is_valid():
        try:
            AdminService().update_catalog_item(project, form.cleaned_data)
            return redirect('/admin/projects/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    return render(request, 'admin/project_edit.html', {'form': form, 'project': project})


@staff_required
def admin_users_view(request):
    return render(request, 'admin/users.html', AdminService().list_users_context())


@staff_required
def admin_payments_view(request):
    return render(request, 'admin/payments.html', AdminService().payments_context())


@staff_required
def admin_user_project_edit_view(request, user_project_id):
    user_project = get_object_or_404(UserProject, pk=user_project_id)
    form = UserProjectAdminForm(request.POST or None, request.FILES or None, instance=user_project)
    if request.method == 'POST' and form.is_valid():
        try:
            AdminService().update_user_project(user_project, form.cleaned_data, request.FILES.get('delivery_file'))
            return redirect('/admin/users/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    return render(request, 'admin/user_project_edit.html', {'form': form, 'user_project': user_project})
