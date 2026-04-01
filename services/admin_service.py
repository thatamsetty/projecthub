from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.payments.models import Payment
from apps.projects.models import AdminActionLog, Notification, ProjectCatalog, ProjectDeliverable, UserProject
from services.notification_service import NotificationService
from services.storage_service import FileUploadService

User = get_user_model()


class AdminService:
    DEFAULT_INSTALLMENTS = (30, 40, 30)
    PAYMENT_OVERDUE_HOURS = 72
    DELIVERY_MAX_UPLOAD_SIZE = 100 * 1024 * 1024

    def __init__(self, actor=None):
        self.actor = actor
        self.notifications = NotificationService()
        self.storage = FileUploadService()

    def dashboard_summary(self):
        return {
            'catalog_count': ProjectCatalog.objects.count(),
            'user_count': User.objects.filter(is_staff=False).count(),
            'active_projects': UserProject.objects.exclude(status=UserProject.Status.DELIVERED).count(),
            'revenue': Payment.objects.filter(status=Payment.PaymentStatus.SUCCESS).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'unread_notifications': Notification.objects.filter(is_read=False).count(),
            'payments_in_verification': Payment.objects.filter(status=Payment.PaymentStatus.VERIFICATION).count(),
        }

    def list_project_catalog_context(self):
        return {'catalog_items': ProjectCatalog.objects.all()}

    def create_catalog_item(self, validated_data):
        self._ensure_staff()
        return ProjectCatalog.objects.create(**validated_data)

    def update_catalog_item(self, project, validated_data):
        self._ensure_staff()
        for field, value in validated_data.items():
            setattr(project, field, value)
        project.save()
        return project

    def list_users_context(self):
        return {
            'users': User.objects.filter(is_staff=False).prefetch_related('user_projects__project', 'user_projects__payments'),
            'user_projects': UserProject.objects.select_related('user', 'project').prefetch_related('payments', 'notifications'),
        }

    def payments_context(self):
        return {
            'payments': Payment.objects.select_related('user', 'user_project', 'user_project__project', 'reviewed_by')
        }

    def payment_users_context(self, *, search='', payment_filter='all'):
        search = (search or '').strip()
        payment_filter = (payment_filter or 'all').strip().lower()
        users = User.objects.filter(is_staff=False).prefetch_related(
            Prefetch(
                'user_projects',
                queryset=UserProject.objects.select_related('project').prefetch_related(
                    Prefetch(
                        'payments',
                        queryset=Payment.objects.select_related('reviewed_by').order_by('-created_at'),
                    )
                ),
            )
        )

        rows = []
        for user in users:
            name = user.get_full_name().strip() if hasattr(user, 'get_full_name') else ''
            display_name = name or user.username
            if search:
                search_lower = search.lower()
                in_name = search_lower in display_name.lower() or search_lower in user.username.lower()
                in_email = search_lower in (user.email or '').lower()
                if not in_name and not in_email:
                    continue

            projects = list(user.user_projects.all())
            total_projects = len(projects)
            total_project_amount = sum((project.total_price or Decimal('0.00')) for project in projects)
            total_paid = Decimal('0.00')
            has_pending = False
            has_overdue = False

            for project in projects:
                total_paid += project.paid_amount or Decimal('0.00')
                latest_by_stage = self._latest_payments_by_stage(project.payments.all())
                for payment in latest_by_stage.values():
                    if payment.status == Payment.PaymentStatus.SUCCESS:
                        continue
                    if payment.status in {Payment.PaymentStatus.REQUESTED, Payment.PaymentStatus.VERIFICATION}:
                        has_pending = True
                        if self._is_payment_overdue(payment):
                            has_overdue = True
                    elif payment.status == Payment.PaymentStatus.REJECTED:
                        has_pending = True

            pending_amount = max(total_project_amount - total_paid, Decimal('0.00'))
            has_pending = has_pending or (pending_amount > Decimal('0.00'))
            is_completed = total_projects > 0 and pending_amount <= Decimal('0.00')

            if payment_filter == 'pending' and not has_pending:
                continue
            if payment_filter == 'completed' and not is_completed:
                continue

            rows.append({
                'id': user.id,
                'name': display_name,
                'email': user.email,
                'total_projects': total_projects,
                'total_paid': total_paid,
                'pending_amount': pending_amount,
                'has_pending': has_pending,
                'has_overdue': has_overdue,
                'is_completed': is_completed,
            })

        rows.sort(key=lambda row: (row['name'] or '').lower())
        return {
            'users': rows,
            'search': search,
            'selected_filter': payment_filter if payment_filter in {'all', 'pending', 'completed'} else 'all',
        }

    def payment_user_projects_context(self, user_id):
        user = get_object_or_404(
            User.objects.filter(is_staff=False).prefetch_related(
                Prefetch(
                    'user_projects',
                    queryset=UserProject.objects.select_related('project').prefetch_related(
                        Prefetch('payments', queryset=Payment.objects.order_by('-created_at'))
                    ),
                )
            ),
            pk=user_id,
        )
        projects = []
        for user_project in user.user_projects.all():
            total_amount = user_project.total_price or Decimal('0.00')
            paid_amount = user_project.paid_amount or Decimal('0.00')
            payment_progress_percent = int((paid_amount / total_amount) * 100) if total_amount > 0 else 0
            payment_progress_percent = max(0, min(payment_progress_percent, 100))
            projects.append({
                'id': user_project.id,
                'title': user_project.project.title,
                'status': self._project_status_group(user_project.status),
                'status_label': user_project.get_status_display(),
                'total_cost': total_amount,
                'paid_amount': paid_amount,
                'progress_percent': payment_progress_percent,
            })
        projects.sort(key=lambda row: row['title'].lower())
        display_name = user.get_full_name().strip() if hasattr(user, 'get_full_name') else ''
        return {
            'selected_user': user,
            'selected_user_name': display_name or user.username,
            'projects': projects,
        }

    def payment_project_detail_context(self, user_project_id):
        user_project = get_object_or_404(
            UserProject.objects.select_related('user', 'project').prefetch_related(
                Prefetch('payments', queryset=Payment.objects.select_related('reviewed_by').order_by('-created_at')),
                Prefetch('audit_logs', queryset=AdminActionLog.objects.select_related('actor').order_by('-created_at')),
            ),
            pk=user_project_id,
        )
        total_amount = user_project.total_price or Decimal('0.00')
        paid_amount = user_project.paid_amount or Decimal('0.00')
        paid_percent = int((paid_amount / total_amount) * 100) if total_amount > 0 else 0
        paid_percent = max(0, min(paid_percent, 100))

        latest_by_stage = self._latest_payments_by_stage(user_project.payments.all())
        stage_rows = []
        overdue_count = 0
        for stage_info in user_project.payment_stage_breakdown:
            stage = stage_info['stage']
            latest_payment = latest_by_stage.get(stage)
            amount = stage_info['amount'] or Decimal('0.00')
            is_unlocked = self._is_stage_unlocked(user_project, stage, latest_by_stage)
            stage_status = self._payment_stage_status(latest_payment, is_unlocked)
            is_overdue = bool(latest_payment and self._is_payment_overdue(latest_payment))
            if is_overdue:
                stage_status = 'overdue'
                overdue_count += 1
            stage_rows.append({
                'stage': stage,
                'label': stage_info['label'],
                'amount': amount,
                'is_unlocked': is_unlocked,
                'status': stage_status,
                'status_label': self._payment_stage_status_label(stage_status),
                'payment': latest_payment,
                'can_approve_reject': bool(latest_payment and latest_payment.status == Payment.PaymentStatus.VERIFICATION),
                'can_send_reminder': bool(latest_payment and latest_payment.status in {
                    Payment.PaymentStatus.REQUESTED,
                    Payment.PaymentStatus.VERIFICATION,
                    Payment.PaymentStatus.REJECTED,
                }),
            })

        payment_history = list(user_project.payments.all())
        audit_logs = list(user_project.audit_logs.all())
        can_download_invoice = total_amount > 0

        return {
            'user_project': user_project,
            'total_amount': total_amount,
            'paid_amount': paid_amount,
            'pending_amount': max(total_amount - paid_amount, Decimal('0.00')),
            'paid_percent': paid_percent,
            'stage_rows': stage_rows,
            'payment_history': payment_history,
            'audit_logs': audit_logs,
            'overdue_count': overdue_count,
            'can_download_invoice': can_download_invoice,
        }

    @transaction.atomic
    def approve_project(self, user_project, total_price, installment_percentages=None):
        self._ensure_staff()
        if user_project.status != UserProject.Status.PENDING:
            raise ValidationError('Only pending projects can be approved.')

        total_price = Decimal(total_price).quantize(Decimal('0.01'))
        if total_price <= 0:
            raise ValidationError('Total price must be greater than zero.')

        p1, p2, p3 = self._resolve_installments(total_price, installment_percentages or self.DEFAULT_INSTALLMENTS)
        user_project.total_price = total_price
        user_project.installment_1 = p1
        user_project.installment_2 = p2
        user_project.installment_3 = p3
        user_project.paid_amount = Decimal('0.00')
        user_project.current_stage = UserProject.Stage.STAGE_1
        user_project.payment_requested_for_stage = None
        user_project.status = UserProject.Status.APPROVED
        user_project.agreed = True
        user_project.approved_at = timezone.now()
        user_project.project.base_price = total_price
        user_project.project.is_active = True
        user_project.project.save(update_fields=['base_price', 'is_active', 'updated_at'])
        user_project.save(update_fields=[
            'total_price',
            'installment_1',
            'installment_2',
            'installment_3',
            'paid_amount',
            'current_stage',
            'payment_requested_for_stage',
            'status',
            'agreed',
            'approved_at',
            'updated_at',
        ])
        self._log_action(user_project, 'approve_project', {'total_price': str(total_price), 'installments': [str(p1), str(p2), str(p3)]})
        self.notifications.notify_project_approval(user_project)
        self.request_payment(user_project, UserProject.Stage.STAGE_1)
        return user_project

    @transaction.atomic
    def update_progress(self, user_project, progress, admin_notes=''):
        self._ensure_staff()
        if user_project.status not in {
            UserProject.Status.APPROVED,
            UserProject.Status.IN_PROGRESS,
            UserProject.Status.MID_STAGE,
            UserProject.Status.COMPLETED,
        }:
            raise ValidationError('Progress can only be updated after approval and before delivery.')

        if progress < 0 or progress > 100:
            raise ValidationError('Progress must be between 0 and 100.')

        user_project.progress = progress
        if admin_notes:
            user_project.admin_notes = admin_notes
        stage_label = self._sync_progress_workflow(user_project)
        user_project.save(update_fields=['progress', 'admin_notes', 'status', 'current_stage', 'updated_at'])
        self._log_action(user_project, 'update_progress', {'progress': progress, 'admin_notes': admin_notes})
        self.notifications.notify_progress_update(user_project)
        if stage_label:
            self.notifications.notify_stage_transition(user_project, stage_label)
        self._ensure_automatic_payment_request(user_project)
        return user_project

    @transaction.atomic
    def request_payment(self, user_project, stage):
        self._ensure_staff()
        stage = int(stage)
        self._validate_payment_request(user_project, stage)
        payment_type = self._stage_to_payment_type(stage)
        amount = self._stage_amount(user_project, stage)
        existing_open = user_project.payments.filter(
            stage=stage,
            status__in=[Payment.PaymentStatus.REQUESTED, Payment.PaymentStatus.VERIFICATION],
        ).first()
        if existing_open:
            raise ValidationError(f'Stage {stage} payment is already requested.')

        payment = Payment.objects.create(
            user=user_project.user,
            user_project=user_project,
            stage=stage,
            amount=amount,
            type=payment_type,
            status=Payment.PaymentStatus.REQUESTED,
        )
        user_project.payment_requested_for_stage = stage
        user_project.payment_status = UserProject.PaymentStatus.PENDING
        user_project.payment_proof = ''
        user_project.save(update_fields=['payment_requested_for_stage', 'payment_status', 'payment_proof', 'updated_at'])
        self._log_action(user_project, 'request_payment', {'stage': stage, 'amount': str(amount)})
        self.notifications.notify_payment_request(user_project, stage, amount)
        return payment

    @transaction.atomic
    def mark_stage_complete(self, user_project, stage):
        self._ensure_staff()
        stage = int(stage)
        self._validate_paid_stage(user_project, stage)
        next_stage = stage + 1
        if next_stage <= UserProject.Stage.STAGE_3:
            self.request_payment(user_project, next_stage)
            self._log_action(user_project, 'mark_stage_complete', {'stage': stage, 'next_payment_stage': next_stage})
        else:
            self._log_action(user_project, 'mark_stage_complete', {'stage': stage, 'next_payment_stage': 'delivery'})
        return user_project

    @transaction.atomic
    def deliver_project(self, user_project, delivery_file=None, delivery_url='', admin_notes=''):
        self._ensure_staff()
        if user_project.paid_amount != (user_project.total_price or Decimal('0.00')):
            raise ValidationError('Full payment is required before delivery.')
        if user_project.status not in {UserProject.Status.COMPLETED, UserProject.Status.DELIVERED}:
            raise ValidationError('Project must be completed before delivery.')
        if user_project.status == UserProject.Status.DELIVERED and not delivery_file and not delivery_url:
            raise ValidationError('Upload a new delivery file or URL to add another deliverable version.')

        if delivery_file:
            delivery_url = self.storage.upload(
                delivery_file,
                'projecthub/admin-deliverables',
                max_upload_size=self.DELIVERY_MAX_UPLOAD_SIZE,
            )
        if not delivery_url and not user_project.delivery_url:
            raise ValidationError('Delivery file or URL is required.')

        user_project.delivery_url = delivery_url or user_project.delivery_url
        user_project.admin_notes = admin_notes or user_project.admin_notes
        user_project.progress = 100
        user_project.status = UserProject.Status.DELIVERED
        user_project.current_stage = UserProject.Stage.DELIVERY
        user_project.delivered_at = timezone.now()
        user_project.save(update_fields=['delivery_url', 'admin_notes', 'progress', 'status', 'current_stage', 'delivered_at', 'updated_at'])
        ProjectDeliverable.objects.create(
            user_project=user_project,
            delivery_url=user_project.delivery_url,
            note=admin_notes or '',
            created_by=self.actor if self.actor and self.actor.is_staff else None,
        )
        self._log_action(user_project, 'deliver_project', {'delivery_url': user_project.delivery_url})
        self.notifications.notify_delivery(user_project)
        return user_project

    @transaction.atomic
    def send_manual_notification(self, user_project, title, message):
        self._ensure_staff()
        notification = self.notifications.notify_custom(
            user=user_project.user,
            title=title,
            message=message,
            user_project=user_project,
        )
        self._log_action(user_project, 'manual_notification', {'title': title})
        return notification

    @transaction.atomic
    def register_payment_success(self, payment, gateway_payload=None):
        user_project = payment.user_project
        if payment.status == Payment.PaymentStatus.SUCCESS:
            raise ValidationError('Payment is already verified.')

        payment.status = Payment.PaymentStatus.SUCCESS
        payment.paid_at = timezone.now()
        payment.gateway_payload = gateway_payload or payment.gateway_payload
        payment.reviewed_at = payment.reviewed_at or timezone.now()
        payment.save(update_fields=['status', 'paid_at', 'gateway_payload', 'reviewed_at'])

        user_project.paid_amount = (user_project.paid_amount + payment.amount).quantize(Decimal('0.01'))
        user_project.payment_requested_for_stage = None
        user_project.payment_status = UserProject.PaymentStatus.PAID
        if payment.payment_proof:
            user_project.payment_proof = payment.payment_proof

        stage_label = self._sync_progress_workflow(user_project)

        user_project.save(update_fields=['paid_amount', 'payment_requested_for_stage', 'payment_status', 'payment_proof', 'status', 'current_stage', 'updated_at'])
        self._log_action(user_project, 'payment_success', {'payment_id': payment.id, 'stage': payment.stage, 'amount': str(payment.amount)})
        self.notifications.notify_payment_success(user_project, payment.stage, payment.amount)
        if stage_label:
            self.notifications.notify_stage_transition(user_project, stage_label)
        self._ensure_automatic_payment_request(user_project)
        return user_project

    def _ensure_staff(self):
        if not self.actor or not self.actor.is_staff:
            raise PermissionDenied('Admin access is required.')

    def _resolve_installments(self, total_price, percentages):
        if len(percentages) != 3 or sum(percentages) != 100:
            raise ValidationError('Installment percentages must contain three values that total 100.')
        parts = []
        remaining = total_price
        for percentage in percentages[:2]:
            value = (total_price * Decimal(percentage) / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            parts.append(value)
            remaining -= value
        parts.append(remaining.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        return tuple(parts)

    def _stage_amount(self, user_project, stage):
        mapping = {
            UserProject.Stage.STAGE_1: user_project.installment_1,
            UserProject.Stage.STAGE_2: user_project.installment_2,
            UserProject.Stage.STAGE_3: user_project.installment_3,
        }
        return mapping.get(stage, Decimal('0.00'))

    def _stage_to_payment_type(self, stage):
        mapping = {
            UserProject.Stage.STAGE_1: Payment.PaymentType.INSTALLMENT_1,
            UserProject.Stage.STAGE_2: Payment.PaymentType.INSTALLMENT_2,
            UserProject.Stage.STAGE_3: Payment.PaymentType.INSTALLMENT_3,
        }
        return mapping[stage]

    def _validate_payment_request(self, user_project, stage):
        if stage not in {UserProject.Stage.STAGE_1, UserProject.Stage.STAGE_2, UserProject.Stage.STAGE_3}:
            raise ValidationError('Only the three installment stages can request payment.')
        if user_project.status == UserProject.Status.PENDING:
            raise ValidationError('Approve the project before requesting payment.')
        if not user_project.total_price:
            raise ValidationError('Set project pricing before requesting payment.')
        if self._has_paid_stage(user_project, stage):
            raise ValidationError(f'Stage {stage} payment is already completed.')
        if stage == UserProject.Stage.STAGE_1 and user_project.status not in {
            UserProject.Status.APPROVED,
            UserProject.Status.IN_PROGRESS,
            UserProject.Status.MID_STAGE,
            UserProject.Status.COMPLETED,
        }:
            raise ValidationError('Stage 1 payment can only be requested after approval.')
        if stage == UserProject.Stage.STAGE_2:
            if not self._has_paid_stage(user_project, UserProject.Stage.STAGE_1):
                raise ValidationError('Stage 2 payment can only be requested after Stage 1 is paid.')
            if user_project.progress < 55:
                raise ValidationError('Stage 2 payment unlocks automatically once progress reaches 55%.')
        if stage == UserProject.Stage.STAGE_3:
            if not self._has_paid_stage(user_project, UserProject.Stage.STAGE_2):
                raise ValidationError('Stage 3 payment can only be requested after Stage 2 is paid.')
            if user_project.progress < 100:
                raise ValidationError('Stage 3 payment unlocks automatically once progress reaches 100%.')

    def _validate_paid_stage(self, user_project, stage):
        if not self._has_paid_stage(user_project, stage):
            raise ValidationError(f'Stage {stage} payment must be completed first.')

    def _has_paid_stage(self, user_project, stage):
        return user_project.payments.filter(stage=stage, status=Payment.PaymentStatus.SUCCESS).exists()

    def _has_open_stage_payment(self, user_project, stage):
        return user_project.payments.filter(
            stage=stage,
            status__in=[Payment.PaymentStatus.REQUESTED, Payment.PaymentStatus.VERIFICATION],
        ).exists()

    def _sync_progress_workflow(self, user_project):
        previous_status = user_project.status
        previous_stage = user_project.current_stage

        if user_project.status == UserProject.Status.DELIVERED:
            return None

        if user_project.progress >= 100:
            next_status = UserProject.Status.COMPLETED
            next_stage = UserProject.Stage.STAGE_3
            stage_label = 'Completed'
        elif user_project.progress >= 55:
            next_status = UserProject.Status.MID_STAGE
            next_stage = UserProject.Stage.STAGE_2
            stage_label = 'Mid Stage'
        elif user_project.progress > 0 or self._has_paid_stage(user_project, UserProject.Stage.STAGE_1):
            next_status = UserProject.Status.IN_PROGRESS
            next_stage = UserProject.Stage.STAGE_1
            stage_label = 'In Progress'
        else:
            next_status = UserProject.Status.APPROVED
            next_stage = UserProject.Stage.STAGE_1
            stage_label = None

        user_project.status = next_status
        user_project.current_stage = next_stage

        if previous_status != next_status or previous_stage != next_stage:
            return stage_label
        return None

    def _ensure_automatic_payment_request(self, user_project):
        if user_project.payment_requested_for_stage or not user_project.total_price:
            return None

        if not self._has_paid_stage(user_project, UserProject.Stage.STAGE_1) and not self._has_open_stage_payment(user_project, UserProject.Stage.STAGE_1):
            if user_project.status in {
                UserProject.Status.APPROVED,
                UserProject.Status.IN_PROGRESS,
                UserProject.Status.MID_STAGE,
                UserProject.Status.COMPLETED,
            }:
                return self.request_payment(user_project, UserProject.Stage.STAGE_1)

        if (
            user_project.progress >= 55
            and self._has_paid_stage(user_project, UserProject.Stage.STAGE_1)
            and not self._has_paid_stage(user_project, UserProject.Stage.STAGE_2)
            and not self._has_open_stage_payment(user_project, UserProject.Stage.STAGE_2)
        ):
            return self.request_payment(user_project, UserProject.Stage.STAGE_2)

        if (
            user_project.progress >= 100
            and self._has_paid_stage(user_project, UserProject.Stage.STAGE_2)
            and not self._has_paid_stage(user_project, UserProject.Stage.STAGE_3)
            and not self._has_open_stage_payment(user_project, UserProject.Stage.STAGE_3)
        ):
            return self.request_payment(user_project, UserProject.Stage.STAGE_3)

        return None

    def _log_action(self, user_project, action, details):
        if self.actor and self.actor.is_staff:
            AdminActionLog.objects.create(actor=self.actor, user_project=user_project, action=action, details=details)

    def _latest_payments_by_stage(self, payments):
        latest = {}
        for payment in payments:
            if payment.stage not in latest:
                latest[payment.stage] = payment
        return latest

    def _is_stage_unlocked(self, user_project, stage, latest_by_stage):
        if stage == UserProject.Stage.STAGE_1:
            return user_project.status != UserProject.Status.PENDING and bool(user_project.total_price)
        if stage == UserProject.Stage.STAGE_2:
            stage_1 = latest_by_stage.get(UserProject.Stage.STAGE_1)
            return bool(stage_1 and stage_1.status == Payment.PaymentStatus.SUCCESS and user_project.progress >= 55)
        if stage == UserProject.Stage.STAGE_3:
            stage_2 = latest_by_stage.get(UserProject.Stage.STAGE_2)
            return bool(stage_2 and stage_2.status == Payment.PaymentStatus.SUCCESS and user_project.progress >= 100)
        return False

    def _payment_stage_status(self, payment, is_unlocked):
        if payment:
            if payment.status == Payment.PaymentStatus.SUCCESS:
                return 'paid'
            if payment.status in {Payment.PaymentStatus.REQUESTED, Payment.PaymentStatus.VERIFICATION}:
                return 'pending'
            if payment.status == Payment.PaymentStatus.REJECTED:
                return 'rejected'
        return 'pending' if is_unlocked else 'locked'

    def _payment_stage_status_label(self, status):
        mapping = {
            'paid': 'Paid',
            'pending': 'Pending',
            'locked': 'Locked',
            'rejected': 'Rejected',
            'overdue': 'Overdue',
        }
        return mapping.get(status, status.title())

    def _is_payment_overdue(self, payment):
        if payment.status not in {Payment.PaymentStatus.REQUESTED, Payment.PaymentStatus.VERIFICATION}:
            return False
        anchor = payment.proof_uploaded_at or payment.requested_at or payment.created_at
        if not anchor:
            return False
        return anchor <= timezone.now() - timedelta(hours=self.PAYMENT_OVERDUE_HOURS)

    def _project_status_group(self, status):
        if status in {UserProject.Status.COMPLETED, UserProject.Status.DELIVERED}:
            return 'completed'
        if status in {UserProject.Status.APPROVED, UserProject.Status.IN_PROGRESS, UserProject.Status.MID_STAGE}:
            return 'in_progress'
        return 'pending'
