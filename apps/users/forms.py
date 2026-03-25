from django import forms
from django.contrib.auth.forms import AuthenticationForm

from apps.users.models import User


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'mobile', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your username',
        })
        self.fields['email'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your email address',
        })
        self.fields['mobile'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your mobile number',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Create a password',
        })
        self.fields['confirm_password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Confirm your password',
        })

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data


class OTPVerificationForm(forms.Form):
    email = forms.EmailField()
    otp_code = forms.CharField(max_length=6)


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(label='Email or Username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your email or username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your password',
        })
