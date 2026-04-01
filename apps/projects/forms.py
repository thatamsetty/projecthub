from django import forms

from apps.projects.models import ProjectCatalog, UserProject

WORKFLOW_STAGE_CHOICES = UserProject.Stage.choices[:3]
MAX_DELIVERY_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class BaseUserProjectForm(forms.Form):
    project_title = forms.CharField(max_length=255)
    tech_stack = forms.CharField(max_length=255, required=False)
    custom_description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    attachment = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project_title'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter your project title',
        })
        self.fields['tech_stack'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Preferred stack, language, or tools',
        })
        self.fields['custom_description'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Describe your requirements, features, delivery expectations, and references.',
        })
        self.fields['attachment'].widget.attrs.update({
            'class': 'form-control',
        })


class UserProjectSubmissionForm(BaseUserProjectForm):
    pass


class UserProjectUpdateForm(BaseUserProjectForm):
    pass


class ProjectCatalogForm(forms.ModelForm):
    class Meta:
        model = ProjectCatalog
        fields = ['title', 'description', 'tech_stack', 'base_price', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'tech_stack': forms.TextInput(attrs={'class': 'form-control'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProjectApprovalForm(forms.Form):
    total_price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    installment_1_percentage = forms.IntegerField(min_value=1, max_value=100, initial=30)
    installment_2_percentage = forms.IntegerField(min_value=1, max_value=100, initial=40)
    installment_3_percentage = forms.IntegerField(min_value=1, max_value=100, initial=30)

    def clean(self):
        cleaned_data = super().clean()
        total = sum([
            cleaned_data.get('installment_1_percentage') or 0,
            cleaned_data.get('installment_2_percentage') or 0,
            cleaned_data.get('installment_3_percentage') or 0,
        ])
        if total != 100:
            raise forms.ValidationError('Installment percentages must total 100.')
        return cleaned_data


class ProjectProgressForm(forms.Form):
    progress = forms.IntegerField(min_value=0, max_value=100)
    admin_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))


class PaymentRequestAdminForm(forms.Form):
    stage = forms.ChoiceField(choices=WORKFLOW_STAGE_CHOICES)


class StageCompletionForm(forms.Form):
    stage = forms.ChoiceField(choices=WORKFLOW_STAGE_CHOICES)


class ProjectDeliveryForm(forms.Form):
    delivery_file = forms.FileField(required=False)
    delivery_url = forms.URLField(required=False)
    admin_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def clean_delivery_file(self):
        delivery_file = self.cleaned_data.get('delivery_file')
        if delivery_file and delivery_file.size > MAX_DELIVERY_FILE_SIZE:
            raise forms.ValidationError('Delivery file must be 100 MB or smaller.')
        return delivery_file


class ManualNotificationForm(forms.Form):
    title = forms.CharField(max_length=255)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))
