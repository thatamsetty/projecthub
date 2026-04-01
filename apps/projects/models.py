from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ProjectCatalog(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    tech_stack = models.CharField(max_length=255)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class UserProject(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        IN_PROGRESS = 'in_progress', 'In Progress'
        MID_STAGE = 'mid_stage', 'Mid Stage'
        COMPLETED = 'completed', 'Completed'
        DELIVERED = 'delivered', 'Delivered'

    class Stage(models.IntegerChoices):
        STAGE_1 = 1, 'Stage 1'
        STAGE_2 = 2, 'Stage 2'
        STAGE_3 = 3, 'Stage 3'
        DELIVERY = 4, 'Delivery'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFICATION = 'verification', 'Verification'
        PAID = 'paid', 'Paid'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_projects')
    project = models.ForeignKey(ProjectCatalog, on_delete=models.CASCADE, related_name='user_projects')
    custom_description = models.TextField()
    attachment_url = models.URLField(blank=True)
    delivery_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    progress = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    installment_1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    installment_2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    installment_3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_stage = models.PositiveSmallIntegerField(choices=Stage.choices, default=Stage.STAGE_1)
    payment_proof = models.FileField(upload_to='payment-proofs/', blank=True)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_requested_for_stage = models.PositiveSmallIntegerField(choices=Stage.choices, null=True, blank=True)
    agreed = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    @property
    def effective_price(self):
        return self.total_price if self.total_price is not None else self.project.base_price

    @property
    def outstanding_amount(self):
        total = self.total_price or Decimal('0.00')
        return max(total - self.paid_amount, Decimal('0.00'))

    @property
    def can_download(self):
        has_deliverable = bool(self.delivery_url) or self.deliverables.exists()
        return self.status == self.Status.DELIVERED and has_deliverable and self.paid_amount == (self.total_price or Decimal('0.00'))

    @property
    def can_user_edit(self):
        return self.status == self.Status.PENDING

    @property
    def payment_stage_breakdown(self):
        return [
            {'stage': 1, 'label': 'Stage 1', 'amount': self.installment_1},
            {'stage': 2, 'label': 'Stage 2', 'amount': self.installment_2},
            {'stage': 3, 'label': 'Stage 3', 'amount': self.installment_3},
        ]

    @property
    def active_payment_amount(self):
        if self.payment_requested_for_stage == self.Stage.STAGE_1:
            return self.installment_1
        if self.payment_requested_for_stage == self.Stage.STAGE_2:
            return self.installment_2
        if self.payment_requested_for_stage == self.Stage.STAGE_3:
            return self.installment_3
        return Decimal('0.00')

    def __str__(self):
        return f'{self.user.username} - {self.project.title}'


class ProjectDeliverable(models.Model):
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name='deliverables')
    delivery_url = models.URLField()
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='project_deliveries')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Deliverable {self.id} - Project {self.user_project_id}'


class Notification(models.Model):
    class Type(models.TextChoices):
        APPROVAL = 'approval', 'Approval'
        PAYMENT = 'payment', 'Payment'
        PROGRESS = 'progress', 'Progress'
        STAGE = 'stage', 'Stage Transition'
        DELIVERY = 'delivery', 'Delivery'
        SYSTEM = 'system', 'System'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=Type.choices)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def __str__(self):
        return f'{self.user.username} - {self.title}'


class AdminActionLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_action_logs')
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=120)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.actor.username} - {self.action}'
