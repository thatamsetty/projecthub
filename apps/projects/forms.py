from django import forms

from apps.projects.models import ProjectCatalog, UserProject


class UserProjectSubmissionForm(forms.Form):
    project_id = forms.IntegerField(widget=forms.HiddenInput)
    custom_description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    attachment = forms.FileField(required=False)


class ProjectCatalogForm(forms.ModelForm):
    class Meta:
        model = ProjectCatalog
        fields = ['title', 'description', 'tech_stack', 'base_price', 'is_active']


class UserProjectAdminForm(forms.ModelForm):
    delivery_file = forms.FileField(required=False)

    class Meta:
        model = UserProject
        fields = ['status', 'progress', 'custom_price', 'agreed', 'delivery_url']
