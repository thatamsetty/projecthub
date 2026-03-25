from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch

from apps.payments.models import Payment
from apps.projects.models import ProjectCatalog, UserProject
from services.notification_service import NotificationService
from services.storage_service import FileUploadService


class ProjectQueryService:
    def list_active_catalog(self):
        return ProjectCatalog.objects.filter(is_active=True)

    def list_user_projects(self, user):
        projects = UserProject.objects.filter(user=user).select_related('project').prefetch_related('payments')
        return [self._attach_payment_summary(item) for item in projects]

    def get_user_project_for_user(self, user, user_project_id):
        user_project = UserProject.objects.select_related('project', 'user').prefetch_related('payments').get(pk=user_project_id, user=user)
        return self._attach_payment_summary(user_project)

    def list_downloadable_projects(self, user):
        return [item for item in self.list_user_projects(user) if item.can_download and item.delivery_url]

    def _attach_payment_summary(self, user_project):
        payments = list(user_project.payments.all())
        user_project.payment_summary = {
            'advance_paid': any(p.type == Payment.PaymentType.ADVANCE and p.status == Payment.PaymentStatus.SUCCESS for p in payments),
            'final_paid': any(p.type == Payment.PaymentType.FINAL and p.status == Payment.PaymentStatus.SUCCESS for p in payments),
        }
        return user_project


class ProjectCommandService:
    def __init__(self):
        self.storage = FileUploadService()
        self.notifications = NotificationService()

    @transaction.atomic
    def create_user_project(self, user, validated_data, uploaded_file):
        project = ProjectCatalog.objects.filter(pk=validated_data['project_id'], is_active=True).first()
        if not project:
            raise ValidationError('Selected catalog project is not available.')
        attachment_url = self.storage.upload(uploaded_file, 'projecthub/user-submissions') if uploaded_file else ''
        return UserProject.objects.create(
            user=user,
            project=project,
            custom_description=validated_data['custom_description'],
            attachment_url=attachment_url,
            status=UserProject.Status.REQUESTED,
        )

    @transaction.atomic
    def approve_project(self, user_project_id, price):
        user_project = UserProject.objects.select_related('user', 'project').get(pk=user_project_id)
        user_project.custom_price = price
        user_project.status = UserProject.Status.APPROVED
        user_project.agreed = True
        user_project.save(update_fields=['custom_price', 'status', 'agreed', 'updated_at'])
        self.notifications.send_project_approval(user_project.user.email, user_project.project.title, user_project.effective_price)
        return user_project

    @transaction.atomic
    def update_project_progress(self, user_project_id, progress):
        user_project = UserProject.objects.select_related('user', 'project').get(pk=user_project_id)
        user_project.progress = progress
        if progress > 0 and user_project.status == UserProject.Status.APPROVED:
            user_project.status = UserProject.Status.IN_PROGRESS
        user_project.save(update_fields=['progress', 'status', 'updated_at'])
        self.notifications.send_progress_update(user_project.user.email, user_project.project.title, progress)
        return user_project

    @transaction.atomic
    def attach_delivery(self, user_project_id, uploaded_file):
        user_project = UserProject.objects.get(pk=user_project_id)
        delivery_url = self.storage.upload(uploaded_file, 'projecthub/admin-deliverables') if uploaded_file else user_project.delivery_url
        user_project.delivery_url = delivery_url
        user_project.save(update_fields=['delivery_url', 'updated_at'])
        return user_project
