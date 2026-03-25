import random
from datetime import timedelta

from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.users.models import OTPRequest, User
from services.notification_service import NotificationService


class UserAuthService:
    def initiate_registration(self, validated_data):
        if User.objects.filter(email=validated_data['email']).exists():
            raise ValidationError('Email already registered.')
        if User.objects.filter(username=validated_data['username']).exists():
            raise ValidationError('Username already registered.')
        if User.objects.filter(mobile=validated_data['mobile']).exists():
            raise ValidationError('Mobile already registered.')

        otp = f"{random.randint(100000, 999999)}"
        OTPRequest.objects.filter(email=validated_data['email'], purpose='register', is_verified=False).delete()
        OTPRequest.objects.create(
            email=validated_data['email'],
            otp_code=otp,
            purpose='register',
            username=validated_data['username'],
            mobile=validated_data['mobile'],
            password=validated_data['password'],
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        NotificationService().send_otp(validated_data['email'], otp)
        return otp

    def complete_registration(self, email, otp_code):
        otp_request = OTPRequest.objects.filter(email=email, purpose='register', is_verified=False).first()
        if not otp_request or otp_request.is_expired() or otp_request.otp_code != otp_code:
            raise ValidationError('Invalid or expired OTP.')

        user = User.objects.create_user(
            username=otp_request.username,
            email=otp_request.email,
            mobile=otp_request.mobile,
            password=otp_request.password,
        )
        otp_request.is_verified = True
        otp_request.save(update_fields=['is_verified'])
        return user

    def login(self, request, username_or_email, password):
        user = User.objects.filter(email=username_or_email).first()
        username = user.username if user else username_or_email
        authenticated_user = authenticate(request, username=username, password=password)
        if authenticated_user:
            login(request, authenticated_user)
        return authenticated_user
