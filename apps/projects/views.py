import os
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.projects.forms import UserProjectSubmissionForm, UserProjectUpdateForm
from apps.projects.models import ProjectCatalog, ProjectDeliverable, UserProject
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
    initial = {}
    project_id = request.GET.get('project_id')
    if project_id:
        project = ProjectCatalog.objects.filter(pk=project_id, is_active=True).first()
        if project:
            initial['project_title'] = project.title
            initial['tech_stack'] = project.tech_stack
            initial['custom_description'] = project.description
    form = UserProjectSubmissionForm(request.POST or None, request.FILES or None, initial=initial)
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
    form = None
    if user_project.can_user_edit:
        form = UserProjectUpdateForm(
            request.POST or None,
            request.FILES or None,
            initial={
                'project_title': user_project.project.title,
                'tech_stack': user_project.project.tech_stack,
                'custom_description': user_project.custom_description,
            },
        )
        if request.method == 'POST' and form.is_valid():
            try:
                ProjectCommandService().update_user_project_submission(request.user, user_project, form.cleaned_data, request.FILES.get('attachment'))
                return redirect(f'/dashboard/projects/{user_project.id}/')
            except ValidationError as exc:
                form.add_error(None, exc.message)
    return render(request, 'user/user_project_detail.html', {
        'user_project': user_project,
        'form': form,
    })


@login_required
def downloads_view(request):
    completed_projects = ProjectQueryService().list_downloadable_projects(request.user)
    return render(request, 'user/downloads.html', {'completed_projects': completed_projects})


def _build_delivery_response(delivery_url):
    media_url = (settings.MEDIA_URL or '/media/').rstrip('/')
    if delivery_url.startswith(f'{media_url}/'):
        relative_path = delivery_url[len(media_url) + 1:]
        relative_path = unquote(relative_path).replace('\\', '/')
        absolute_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, relative_path))
        media_root_abs = os.path.abspath(str(settings.MEDIA_ROOT))

        if not absolute_path.startswith(media_root_abs):
            raise Http404('Invalid file path.')
        if not os.path.exists(absolute_path):
            raise Http404('File not found.')

        filename = os.path.basename(absolute_path)
        return FileResponse(open(absolute_path, 'rb'), as_attachment=True, filename=filename)
    return redirect(delivery_url)


@login_required
def download_deliverable_view(request, project_id, delivery_id=None):
    user_project = ProjectQueryService().get_user_project_for_user(request.user, project_id)
    if not user_project.can_download:
        raise Http404('Deliverable is not available for download.')

    if delivery_id is not None:
        deliverable = get_object_or_404(ProjectDeliverable, pk=delivery_id, user_project=user_project)
        return _build_delivery_response(deliverable.delivery_url)

    latest = user_project.deliverables.first()
    if latest:
        return _build_delivery_response(latest.delivery_url)
    if user_project.delivery_url:
        return _build_delivery_response(user_project.delivery_url)
    raise Http404('Deliverable is not available for download.')
