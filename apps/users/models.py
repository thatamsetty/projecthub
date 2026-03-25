from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    REQUIRED_FIELDS = ['email', 'mobile']

    def __str__(self):
        return self.username


class OTPRequest(models.Model):
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=32, default='register')
    username = models.CharField(max_length=150, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    password = models.CharField(max_length=128, blank=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        return timezone.now() > self.expires_at
