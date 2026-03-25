from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.projects.models import UserProject


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        ADVANCE = 'ADVANCE', 'Advance'
        FINAL = 'FINAL', 'Final'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=PaymentType.choices)
    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    razorpay_order_id = models.CharField(max_length=120, blank=True)
    razorpay_payment_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_project_id} - {self.type} - {self.status}'
