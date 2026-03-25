from django import forms
from django.contrib.auth.forms import AuthenticationForm

from apps.projects.forms import ProjectCatalogForm, UserProjectAdminForm


class AdminLoginForm(AuthenticationForm):
    username = forms.CharField(label='Email or Username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your admin email or username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Enter your password',
        })
