from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from apps.users.models import User


class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(label='First Name', max_length=150)
    last_name = forms.CharField(label='Second Name', max_length=150, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'mobile', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Choose a username...',
            'autocomplete': 'username',
            'autofocus': 'autofocus',
        })
        self.fields['first_name'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your first name...',
            'autocomplete': 'given-name',
        })
        self.fields['last_name'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your second name...',
            'autocomplete': 'family-name',
        })
        self.fields['email'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your email address...',
            'autocomplete': 'email',
        })
        self.fields['mobile'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your mobile number...',
            'autocomplete': 'tel',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your password...',
            'data-password-toggle-target': 'true',
            'autocomplete': 'new-password',
        })
        self.fields['confirm_password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your password again...',
            'data-password-toggle-target': 'true',
            'autocomplete': 'new-password',
        })

    def clean_username(self):
        return self.cleaned_data['username'].strip()

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_mobile(self):
        return self.cleaned_data['mobile'].strip()

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        candidate_user = User(
            username=(self.data.get('username') or '').strip(),
            email=(self.data.get('email') or '').strip().lower(),
            first_name=(self.data.get('first_name') or '').strip(),
            last_name=(self.data.get('last_name') or '').strip(),
        )
        validate_password(password, user=candidate_user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data


class OTPVerificationForm(forms.Form):
    email = forms.EmailField()
    otp_code = forms.CharField(max_length=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your email address',
        })
        self.fields['otp_code'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter the 6-digit OTP',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
        })


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(label='Username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your username',
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your password',
            'data-password-toggle-target': 'true',
            'autocomplete': 'current-password',
        })

    error_messages = {
        'invalid_login': 'Please enter a valid username and password.',
        'inactive': 'This account is inactive.',
    }


class ForgotPasswordEmailForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your account email',
            'autocomplete': 'email',
        })


class ForgotPasswordOTPForm(forms.Form):
    email = forms.EmailField()
    otp_code = forms.CharField(max_length=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your account email',
            'autocomplete': 'email',
        })
        self.fields['otp_code'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter the 6-digit OTP',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
        })


class ForgotPasswordResetForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Create a new password',
            'data-password-toggle-target': 'true',
            'autocomplete': 'new-password',
        })
        self.fields['confirm_password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Confirm your new password',
            'data-password-toggle-target': 'true',
            'autocomplete': 'new-password',
        })

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data
