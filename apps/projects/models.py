from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ProjectCatalog(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    tech_stack = models.CharField(max_length=255)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class UserProject(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Requested'
        APPROVED = 'APPROVED', 'Approved'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_projects')
    project = models.ForeignKey(ProjectCatalog, on_delete=models.CASCADE, related_name='user_projects')
    custom_description = models.TextField()
    attachment_url = models.URLField(blank=True)
    delivery_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    progress = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    agreed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    @property
    def effective_price(self):
        return self.custom_price if self.custom_price is not None else self.project.base_price

    @property
    def can_download(self):
        return self.status == self.Status.COMPLETED and hasattr(self, 'payment_summary') and self.payment_summary.get('final_paid', False)

    def __str__(self):
        return f'{self.user.username} - {self.project.title}'
