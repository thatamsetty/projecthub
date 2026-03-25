from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from apps.users.forms import OTPVerificationForm, RegisterForm, UserLoginForm
from services.project_service import ProjectQueryService
from services.user_service import UserAuthService


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
            return redirect('/auth/verify-otp/?email=' + form.cleaned_data['email'])
        except ValidationError as exc:
            form.add_error(None, exc.message)
    return render(request, 'user/register.html', {'form': form})


def verify_otp_view(request):
    initial_email = request.GET.get('email', '')
    form = OTPVerificationForm(request.POST or None, initial={'email': initial_email})
    if request.method == 'POST' and form.is_valid():
        try:
            UserAuthService().complete_registration(form.cleaned_data['email'], form.cleaned_data['otp_code'])
            return redirect('/auth/login/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    return render(request, 'user/verify_otp.html', {'form': form})


def login_view(request):
    form = UserLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = UserAuthService().login(request, form.cleaned_data['username'], form.cleaned_data['password'])
        if user:
            return redirect('/dashboard/')
        form.add_error(None, 'Invalid credentials.')
    return render(request, 'user/login.html', {'form': form})


@login_required
def dashboard_view(request):
    projects = ProjectQueryService().list_user_projects(request.user)
    catalog = ProjectQueryService().list_active_catalog()
    return render(request, 'user/dashboard.html', {'user_projects': projects, 'catalog': catalog})


def logout_view(request):
    redirect_url = '/admin-auth/login/' if request.user.is_authenticated and request.user.is_staff else '/auth/login/'
    logout(request)
    return redirect(redirect_url)
