from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.payments.models import Payment
from apps.projects.models import UserProject
from services.admin_service import AdminService
from services.notification_service import NotificationService


class PaymentService:
    OVERDUE_HOURS = 72

    def __init__(self, actor=None):
        self.actor = actor
        self.notifications = NotificationService()

    def list_user_payments(self, user):
        return Payment.objects.filter(user=user).select_related('user_project', 'user_project__project', 'reviewed_by')

    def get_manual_payment_context(self, user, user_project_id, stage):
        user_project = UserProject.objects.select_related('project').prefetch_related('payments').get(pk=user_project_id, user=user)
        payment = self._get_payment_for_stage(user_project, stage)
        if user_project.payment_requested_for_stage != int(stage):
            raise ValidationError('This stage is not open for payment right now.')

        return {
            'user_project': user_project,
            'payment': payment,
            'stage': int(stage),
            'amount': payment.amount,
            'upi_id': '9059964947@ptaxis',
            'qr_image_path': 'images/payments/projecthub-upi-qr.svg',
            'can_upload_proof': payment.status == Payment.PaymentStatus.REQUESTED,
        }

    @transaction.atomic
    def submit_manual_payment_proof(self, user, user_project_id, stage, screenshot, note=''):
        user_project = UserProject.objects.select_for_update().select_related('project').get(pk=user_project_id, user=user)
        payment = self._get_payment_for_stage(user_project, stage, for_update=True)

        if user_project.payment_requested_for_stage != int(stage):
            raise ValidationError('This payment request is no longer active.')
        if payment.status != Payment.PaymentStatus.REQUESTED:
            raise ValidationError('Payment proof has already been uploaded for this stage.')

        payment.payment_proof = screenshot
        payment.payment_note = note
        payment.proof_uploaded_at = timezone.now()
        payment.status = Payment.PaymentStatus.VERIFICATION
        payment.save(update_fields=['payment_proof', 'payment_note', 'proof_uploaded_at', 'status'])

        user_project.payment_proof = screenshot
        user_project.payment_status = UserProject.PaymentStatus.VERIFICATION
        user_project.save(update_fields=['payment_proof', 'payment_status', 'updated_at'])

        self.notifications.notify_payment_proof_uploaded(user_project, payment.stage, payment.amount)
        return payment

    @transaction.atomic
    def approve_manual_payment(self, payment_id, review_note=''):
        self._ensure_staff()
        payment = Payment.objects.select_for_update().select_related('user_project', 'user_project__project').get(pk=payment_id)
        if payment.status != Payment.PaymentStatus.VERIFICATION:
            raise ValidationError('Only payments under verification can be approved.')

        payment.review_note = review_note
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = self.actor
        payment.save(update_fields=['review_note', 'reviewed_at', 'reviewed_by'])
        AdminService(actor=self.actor).register_payment_success(payment, payment.gateway_payload)
        return payment

    @transaction.atomic
    def reject_manual_payment(self, payment_id, review_note):
        self._ensure_staff()
        payment = Payment.objects.select_for_update().select_related('user_project', 'user_project__project').get(pk=payment_id)
        if payment.status != Payment.PaymentStatus.VERIFICATION:
            raise ValidationError('Only payments under verification can be rejected.')

        payment.status = Payment.PaymentStatus.REJECTED
        payment.review_note = review_note
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = self.actor
        payment.save(update_fields=['status', 'review_note', 'reviewed_at', 'reviewed_by'])

        user_project = payment.user_project
        user_project.payment_status = UserProject.PaymentStatus.PENDING
        user_project.payment_proof = ''
        user_project.save(update_fields=['payment_status', 'payment_proof', 'updated_at'])

        self.notifications.notify_payment_rejected(user_project, payment.stage, review_note)
        AdminService(actor=self.actor)._log_action(user_project, 'payment_rejected', {
            'payment_id': payment.id,
            'stage': payment.stage,
            'reason': review_note,
        })

        replacement = Payment.objects.create(
            user=user_project.user,
            user_project=user_project,
            stage=payment.stage,
            amount=payment.amount,
            type=payment.type,
            status=Payment.PaymentStatus.REQUESTED,
        )
        AdminService(actor=self.actor)._log_action(user_project, 'payment_reopened', {
            'payment_id': replacement.id,
            'stage': replacement.stage,
            'amount': str(replacement.amount),
        })
        self.notifications.notify_payment_request(user_project, replacement.stage, replacement.amount)
        return replacement

    @transaction.atomic
    def send_payment_reminder(self, payment_id, note=''):
        self._ensure_staff()
        payment = Payment.objects.select_for_update().select_related('user_project', 'user_project__project', 'user').get(pk=payment_id)
        if payment.status == Payment.PaymentStatus.SUCCESS:
            raise ValidationError('This stage is already paid.')

        message = (
            f'Reminder: please complete or re-upload payment proof for Stage {payment.stage} '
            f'(Rs. {payment.amount}) for {payment.user_project.project.title}.'
        )
        if note:
            message = f'{message} Admin note: {note}'

        self.notifications.notify_custom(
            user=payment.user,
            user_project=payment.user_project,
            title=f'Payment reminder for Stage {payment.stage}',
            message=message,
        )
        AdminService(actor=self.actor)._log_action(payment.user_project, 'payment_reminder', {
            'payment_id': payment.id,
            'stage': payment.stage,
            'note': note,
        })
        return payment

    @transaction.atomic
    def trigger_auto_reminders_for_project(self, user_project):
        self._ensure_staff()
        overdue_cutoff = timezone.now() - timedelta(hours=self.OVERDUE_HOURS)
        overdue_candidates = Payment.objects.select_for_update().filter(
            user_project=user_project,
            status__in=[Payment.PaymentStatus.REQUESTED, Payment.PaymentStatus.VERIFICATION],
        ).filter(
            Q(requested_at__lte=overdue_cutoff) | Q(proof_uploaded_at__lte=overdue_cutoff)
        )

        reminded = 0
        for payment in overdue_candidates:
            self.send_payment_reminder(payment.id, note='Auto reminder for overdue payment stage.')
            reminded += 1
        return reminded

    def _ensure_staff(self):
        if not self.actor or not self.actor.is_staff:
            raise PermissionDenied('Admin access is required.')

    def _get_payment_for_stage(self, user_project, stage, for_update=False):
        queryset = user_project.payments
        if for_update:
            payment = Payment.objects.select_for_update().filter(
                user_project=user_project,
                stage=int(stage),
            ).order_by('-created_at').first()
        else:
            payment = queryset.filter(stage=int(stage)).order_by('-created_at').first()
        if not payment:
            raise ValidationError('This stage payment is not available yet.')
        return payment
