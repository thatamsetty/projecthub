from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.payments.models import Payment
from apps.projects.models import Notification, ProjectCatalog, UserProject
from services.storage_service import FileUploadService


class ProjectQueryService:
    def list_active_catalog(self):
        return ProjectCatalog.objects.filter(is_active=True)

    def list_user_projects(self, user):
        projects = UserProject.objects.filter(user=user).select_related('project').prefetch_related('payments', 'notifications', 'deliverables')
        return [self._attach_project_summary(item) for item in projects]

    def get_user_project_for_user(self, user, user_project_id):
        user_project = UserProject.objects.select_related('project', 'user').prefetch_related('payments', 'notifications', 'audit_logs', 'deliverables').get(
            pk=user_project_id,
            user=user,
        )
        return self._attach_project_summary(user_project)

    def list_downloadable_projects(self, user):
        return [item for item in self.list_user_projects(user) if item.can_download]

    def list_notifications(self, user, limit=10):
        return Notification.objects.filter(user=user).select_related('user_project', 'user_project__project')[:limit]

    def unread_notification_count(self, user):
        return Notification.objects.filter(user=user, is_read=False).count()

    def _attach_project_summary(self, user_project):
        payments = list(user_project.payments.all())
        successful_stages = {payment.stage for payment in payments if payment.status == Payment.PaymentStatus.SUCCESS}
        requested_stages = {payment.stage for payment in payments if payment.status == Payment.PaymentStatus.REQUESTED}
        verification_stages = {payment.stage for payment in payments if payment.status == Payment.PaymentStatus.VERIFICATION}
        user_project.payment_summary = {
            'paid_stage_1': 1 in successful_stages,
            'paid_stage_2': 2 in successful_stages,
            'paid_stage_3': 3 in successful_stages,
            'requested_stage_1': 1 in requested_stages,
            'requested_stage_2': 2 in requested_stages,
            'requested_stage_3': 3 in requested_stages,
            'verification_stage_1': 1 in verification_stages,
            'verification_stage_2': 2 in verification_stages,
            'verification_stage_3': 3 in verification_stages,
            'pending_amount': user_project.outstanding_amount,
            'paid_amount': user_project.paid_amount,
        }
        user_project.timeline = [
            ('Submitted', True),
            ('Approved', user_project.status in {UserProject.Status.APPROVED, UserProject.Status.IN_PROGRESS, UserProject.Status.MID_STAGE, UserProject.Status.COMPLETED, UserProject.Status.DELIVERED}),
            ('In Progress', user_project.status in {UserProject.Status.IN_PROGRESS, UserProject.Status.MID_STAGE, UserProject.Status.COMPLETED, UserProject.Status.DELIVERED}),
            ('Mid Stage', user_project.status in {UserProject.Status.MID_STAGE, UserProject.Status.COMPLETED, UserProject.Status.DELIVERED}),
            ('Completed', user_project.status in {UserProject.Status.COMPLETED, UserProject.Status.DELIVERED}),
            ('Delivered', user_project.status == UserProject.Status.DELIVERED),
        ]
        user_project.delivery_items = list(user_project.deliverables.all())
        return user_project


class ProjectCommandService:
    def __init__(self):
        self.storage = FileUploadService()

    @transaction.atomic
    def create_user_project(self, user, validated_data, uploaded_file):
        project = ProjectCatalog.objects.create(
            title=validated_data['project_title'],
            description=validated_data['custom_description'],
            tech_stack=validated_data.get('tech_stack') or 'Custom Request',
            base_price=0,
            is_active=False,
        )
        attachment_url = self.storage.upload(uploaded_file, 'projecthub/user-submissions') if uploaded_file else ''
        return UserProject.objects.create(
            user=user,
            project=project,
            custom_description=validated_data['custom_description'],
            attachment_url=attachment_url,
            status=UserProject.Status.PENDING,
        )

    @transaction.atomic
    def update_user_project_submission(self, user, user_project, validated_data, uploaded_file):
        if user_project.user_id != user.id:
            raise PermissionDenied('You cannot edit this project.')
        if not user_project.can_user_edit:
            raise ValidationError('Only pending projects can be edited.')

        user_project.project.title = validated_data['project_title']
        user_project.project.description = validated_data['custom_description']
        user_project.project.tech_stack = validated_data.get('tech_stack') or user_project.project.tech_stack
        user_project.project.save(update_fields=['title', 'description', 'tech_stack', 'updated_at'])

        user_project.custom_description = validated_data['custom_description']
        if uploaded_file:
            user_project.attachment_url = self.storage.upload(uploaded_file, 'projecthub/user-submissions')
        user_project.save(update_fields=['custom_description', 'attachment_url', 'updated_at'])
        return user_project

    @transaction.atomic
    def mark_notification_read(self, user, notification_id):
        notification = Notification.objects.get(pk=notification_id, user=user)
        notification.mark_as_read()
        return notification

    @transaction.atomic
    def clear_all_notifications(self, user):
        return Notification.objects.filter(user=user).delete()
