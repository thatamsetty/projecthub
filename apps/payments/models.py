from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.projects.models import UserProject


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        INSTALLMENT_1 = 'installment_1', 'Installment 1'
        INSTALLMENT_2 = 'installment_2', 'Installment 2'
        INSTALLMENT_3 = 'installment_3', 'Installment 3'

    class PaymentStatus(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        VERIFICATION = 'verification', 'Verification'
        SUCCESS = 'success', 'Success'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name='payments')
    stage = models.PositiveSmallIntegerField(choices=UserProject.Stage.choices, default=UserProject.Stage.STAGE_1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=PaymentType.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.REQUESTED)
    payment_proof = models.FileField(upload_to='payment-proofs/', blank=True)
    payment_note = models.CharField(max_length=255, blank=True)
    proof_uploaded_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_payments')
    review_note = models.TextField(blank=True)
    razorpay_order_id = models.CharField(max_length=120, blank=True)
    razorpay_payment_id = models.CharField(max_length=120, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    gateway_payload = models.JSONField(default=dict, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_project_id} - {self.type} - {self.status}'
