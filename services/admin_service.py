from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.payments.models import Payment
from apps.projects.models import ProjectCatalog, UserProject
from services.project_service import ProjectCommandService

User = get_user_model()


class AdminService:
    def dashboard_summary(self):
        return {
            'catalog_count': ProjectCatalog.objects.count(),
            'user_count': User.objects.filter(is_staff=False).count(),
            'active_projects': UserProject.objects.exclude(status=UserProject.Status.COMPLETED).count(),
            'revenue': Payment.objects.filter(status=Payment.PaymentStatus.SUCCESS).aggregate(total=Sum('amount'))['total'] or 0,
        }

    def list_project_catalog_context(self):
        return {'catalog_items': ProjectCatalog.objects.all()}

    def create_catalog_item(self, validated_data):
        return ProjectCatalog.objects.create(**validated_data)

    def update_catalog_item(self, project, validated_data):
        for field, value in validated_data.items():
            setattr(project, field, value)
        project.save()
        return project

    def list_users_context(self):
        return {
            'users': User.objects.filter(is_staff=False).prefetch_related('user_projects__project', 'user_projects__payments'),
            'user_projects': UserProject.objects.select_related('user', 'project').prefetch_related('payments'),
        }

    def payments_context(self):
        return {'payments': Payment.objects.select_related('user', 'user_project', 'user_project__project')}

    def update_user_project(self, user_project, validated_data, delivery_file):
        if validated_data.get('custom_price') is not None:
            ProjectCommandService().approve_project(user_project.id, validated_data['custom_price'])
            user_project.refresh_from_db()
        ProjectCommandService().update_project_progress(user_project.id, validated_data.get('progress', user_project.progress))
        user_project.refresh_from_db()
        if delivery_file:
            ProjectCommandService().attach_delivery(user_project.id, delivery_file)
            user_project.refresh_from_db()
        if validated_data.get('status'):
            user_project.status = validated_data['status']
        user_project.agreed = validated_data.get('agreed', user_project.agreed)
        if validated_data.get('delivery_url'):
            user_project.delivery_url = validated_data['delivery_url']
        if user_project.status == UserProject.Status.COMPLETED and not user_project.payments.filter(
            type=Payment.PaymentType.FINAL,
            status=Payment.PaymentStatus.SUCCESS,
        ).exists():
            raise ValidationError('Final payment must be successful before completion.')
        user_project.save()
        return user_project
