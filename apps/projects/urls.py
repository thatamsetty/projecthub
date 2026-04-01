from django.urls import path

from apps.projects.views import (
    catalog_view,
    download_deliverable_view,
    downloads_view,
    project_detail_view,
    submit_project_view,
    user_project_detail_view,
)

urlpatterns = [
    path('projects/', catalog_view, name='projects'),
    path('projects/<int:project_id>/', project_detail_view, name='project_detail'),
    path('dashboard/projects/<int:project_id>/', user_project_detail_view, name='user_project_detail'),
    path('submit/', submit_project_view, name='submit_project'),
    path('downloads/', downloads_view, name='downloads'),
    path('downloads/<int:project_id>/file/', download_deliverable_view, name='download_deliverable'),
    path('downloads/<int:project_id>/file/<int:delivery_id>/', download_deliverable_view, name='download_deliverable_item'),
]
