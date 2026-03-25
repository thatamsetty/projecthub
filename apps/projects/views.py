from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.projects.forms import UserProjectSubmissionForm
from apps.projects.models import ProjectCatalog, UserProject
from services.project_service import ProjectCommandService, ProjectQueryService


@login_required
def catalog_view(request):
    catalog = ProjectQueryService().list_active_catalog()
    return render(request, 'user/projects.html', {'catalog': catalog})


@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(ProjectCatalog, pk=project_id, is_active=True)
    return render(request, 'user/project_detail.html', {'project': project})


@login_required
def submit_project_view(request):
    form = UserProjectSubmissionForm(request.POST or None, request.FILES or None, initial={'project_id': request.GET.get('project_id')})
    catalog = ProjectQueryService().list_active_catalog()
    if request.method == 'POST' and form.is_valid():
        try:
            ProjectCommandService().create_user_project(request.user, form.cleaned_data, request.FILES.get('attachment'))
            return redirect('/dashboard/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    return render(request, 'user/submit.html', {'form': form, 'catalog': catalog})


@login_required
def user_project_detail_view(request, project_id):
    user_project = ProjectQueryService().get_user_project_for_user(request.user, project_id)
    return render(request, 'user/user_project_detail.html', {'user_project': user_project})


@login_required
def downloads_view(request):
    completed_projects = ProjectQueryService().list_downloadable_projects(request.user)
    return render(request, 'user/downloads.html', {'completed_projects': completed_projects})
