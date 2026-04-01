from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from apps.projects.models import Notification
from apps.users.forms import (
    ForgotPasswordEmailForm,
    ForgotPasswordOTPForm,
    ForgotPasswordResetForm,
    OTPVerificationForm,
    RegisterForm,
    UserLoginForm,
)
from services.project_service import ProjectCommandService, ProjectQueryService
from services.user_service import UserAuthService

PASSWORD_RESET_EMAIL_SESSION_KEY = 'password_reset_email'
PASSWORD_RESET_ROLE_SESSION_KEY = 'password_reset_role'
PASSWORD_RESET_OTP_SESSION_KEY = 'password_reset_otp_verified'
REGISTER_FIRST_NAME_SESSION_KEY = 'register_first_name'
REGISTER_LAST_NAME_SESSION_KEY = 'register_last_name'


def _validation_error_text(exc):
    if hasattr(exc, 'messages') and exc.messages:
        return ' '.join(str(message) for message in exc.messages)
    return str(exc)


def home_redirect_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('/admin-dashboard/')
        return redirect('/dashboard/')
    return redirect('/auth/login/')


def register_view(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            UserAuthService().initiate_registration(form.cleaned_data)
            request.session[REGISTER_FIRST_NAME_SESSION_KEY] = form.cleaned_data.get('first_name', '').strip()
            request.session[REGISTER_LAST_NAME_SESSION_KEY] = form.cleaned_data.get('last_name', '').strip()
            return redirect('/auth/verify-otp/?email=' + form.cleaned_data['email'])
        except ValidationError as exc:
            form.add_error(None, _validation_error_text(exc))
    return render(request, 'user/register.html', {'form': form})


def verify_otp_view(request):
    initial_email = request.GET.get('email', '')
    form = OTPVerificationForm(request.POST or None, initial={'email': initial_email})
    if request.method == 'POST' and form.is_valid():
        try:
            user = UserAuthService().complete_registration(form.cleaned_data['email'], form.cleaned_data['otp_code'])
            first_name = request.session.pop(REGISTER_FIRST_NAME_SESSION_KEY, '').strip()
            last_name = request.session.pop(REGISTER_LAST_NAME_SESSION_KEY, '').strip()
            update_fields = []
            if first_name:
                user.first_name = first_name
                update_fields.append('first_name')
            if last_name:
                user.last_name = last_name
                update_fields.append('last_name')
            if update_fields:
                user.save(update_fields=update_fields)
            return redirect('/auth/login/')
        except ValidationError as exc:
            form.add_error(None, _validation_error_text(exc))
    return render(request, 'user/verify_otp.html', {'form': form})


def login_view(request):
    form = UserLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = UserAuthService().login(request, form.cleaned_data['username'], form.cleaned_data['password'])
        if user:
            return redirect('/dashboard/')
        form.add_error(None, 'Invalid credentials.')
    return render(request, 'user/login.html', {'form': form})


def _password_reset_meta(role):
    if role == 'admin':
        return {
            'role': 'admin',
            'login_url': '/admin-auth/login/',
            'request_url': '/admin-auth/forgot-password/',
            'verify_url': '/admin-auth/forgot-password/verify-otp/',
            'reset_url': '/admin-auth/forgot-password/reset/',
            'role_label': 'Admin',
        }
    return {
        'role': 'user',
        'login_url': '/auth/login/',
        'request_url': '/auth/forgot-password/',
        'verify_url': '/auth/forgot-password/verify-otp/',
        'reset_url': '/auth/forgot-password/reset/',
        'role_label': 'User',
    }


def forgot_password_request_view(request, role='user'):
    meta = _password_reset_meta(role)
    form = ForgotPasswordEmailForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        try:
            UserAuthService().initiate_password_reset(email)
            request.session[PASSWORD_RESET_EMAIL_SESSION_KEY] = email
            request.session[PASSWORD_RESET_ROLE_SESSION_KEY] = meta['role']
            request.session[PASSWORD_RESET_OTP_SESSION_KEY] = False
            return redirect(meta['verify_url'])
        except ValidationError as exc:
            form.add_error(None, _validation_error_text(exc))
    return render(request, 'auth/forgot_password_email.html', {'form': form, 'meta': meta})


def forgot_password_verify_otp_view(request, role='user'):
    meta = _password_reset_meta(role)
    session_email = request.session.get(PASSWORD_RESET_EMAIL_SESSION_KEY, '')
    session_role = request.session.get(PASSWORD_RESET_ROLE_SESSION_KEY, meta['role'])
    if session_role != meta['role']:
        return redirect(meta['request_url'])

    form = ForgotPasswordOTPForm(request.POST or None, initial={'email': session_email})
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        try:
            UserAuthService().verify_password_reset_otp(email, form.cleaned_data['otp_code'])
            request.session[PASSWORD_RESET_EMAIL_SESSION_KEY] = email
            request.session[PASSWORD_RESET_ROLE_SESSION_KEY] = meta['role']
            request.session[PASSWORD_RESET_OTP_SESSION_KEY] = True
            return redirect(meta['reset_url'])
        except ValidationError as exc:
            form.add_error(None, _validation_error_text(exc))
    return render(request, 'auth/forgot_password_verify_otp.html', {'form': form, 'meta': meta})


def forgot_password_reset_view(request, role='user'):
    meta = _password_reset_meta(role)
    session_email = request.session.get(PASSWORD_RESET_EMAIL_SESSION_KEY)
    session_role = request.session.get(PASSWORD_RESET_ROLE_SESSION_KEY)
    otp_verified = request.session.get(PASSWORD_RESET_OTP_SESSION_KEY, False)

    if not session_email or session_role != meta['role'] or not otp_verified:
        return redirect(meta['request_url'])

    form = ForgotPasswordResetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            UserAuthService().reset_password(session_email, form.cleaned_data['new_password'])
            request.session.pop(PASSWORD_RESET_EMAIL_SESSION_KEY, None)
            request.session.pop(PASSWORD_RESET_ROLE_SESSION_KEY, None)
            request.session.pop(PASSWORD_RESET_OTP_SESSION_KEY, None)
            return redirect(meta['login_url'])
        except ValidationError as exc:
            form.add_error(None, _validation_error_text(exc))
    return render(request, 'auth/forgot_password_reset.html', {'form': form, 'meta': meta, 'email': session_email})


@login_required
def dashboard_view(request):
    projects = ProjectQueryService().list_user_projects(request.user)
    catalog = ProjectQueryService().list_active_catalog()
    notifications = ProjectQueryService().list_notifications(request.user)
    return render(request, 'user/dashboard.html', {'user_projects': projects, 'catalog': catalog, 'notifications': notifications})


@login_required
def mark_notification_read_view(request, notification_id):
    if request.method == 'POST':
        try:
            ProjectCommandService().mark_notification_read(request.user, notification_id)
        except Notification.DoesNotExist:
            pass
    return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))


@login_required
def clear_all_notifications_view(request):
    if request.method == 'POST':
        ProjectCommandService().clear_all_notifications(request.user)
    return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))


def logout_view(request):
    UserAuthService().set_online_status(request.user, False)
    redirect_url = '/admin-auth/login/' if request.user.is_authenticated and request.user.is_staff else '/auth/login/'
    logout(request)
    return redirect(redirect_url)
