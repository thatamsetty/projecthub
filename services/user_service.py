import random
from datetime import timedelta

from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
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
        authenticated_user = authenticate(request, username=username_or_email, password=password)
        if authenticated_user:
            login(request, authenticated_user)
            self.set_online_status(authenticated_user, True)
        return authenticated_user

    def set_online_status(self, user, is_online):
        if not user:
            return
        if user.is_online != is_online:
            user.is_online = is_online
            user.save(update_fields=['is_online'])

    def initiate_password_reset(self, email):
        user = User.objects.filter(email=email).first()
        if not user:
            raise ValidationError('No account found with this email.')

        otp = f"{random.randint(100000, 999999)}"
        OTPRequest.objects.filter(email=email, purpose='password_reset', is_verified=False).delete()
        OTPRequest.objects.create(
            email=email,
            otp_code=otp,
            purpose='password_reset',
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        NotificationService().send_otp(email, otp)
        return otp

    def verify_password_reset_otp(self, email, otp_code):
        otp_request = OTPRequest.objects.filter(email=email, purpose='password_reset', is_verified=False).first()
        if not otp_request or otp_request.is_expired() or otp_request.otp_code != otp_code:
            raise ValidationError('Invalid or expired OTP.')

        otp_request.is_verified = True
        otp_request.save(update_fields=['is_verified'])
        return True

    def reset_password(self, email, new_password):
        user = User.objects.filter(email=email).first()
        if not user:
            raise ValidationError('No account found with this email.')

        verify_request = OTPRequest.objects.filter(
            email=email,
            purpose='password_reset',
            is_verified=True,
        ).first()
        if not verify_request:
            raise ValidationError('OTP verification is required before password reset.')

        validate_password(new_password, user=user)
        user.set_password(new_password)
        user.save(update_fields=['password'])
        OTPRequest.objects.filter(email=email, purpose='password_reset').delete()
        return user
