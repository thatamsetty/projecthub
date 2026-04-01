from django import forms
from django.core.exceptions import ValidationError


ALLOWED_IMAGE_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
ALLOWED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def validate_uploaded_image(uploaded_file):
    if not uploaded_file:
        return uploaded_file

    content_type = getattr(uploaded_file, 'content_type', '')
    file_name = (uploaded_file.name or '').lower()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError('Only JPG, PNG, and WEBP image files are allowed.')
    if not file_name.endswith(ALLOWED_IMAGE_EXTENSIONS):
        raise ValidationError('Upload a valid image screenshot in JPG, PNG, or WEBP format.')
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValidationError('Image size must be 5 MB or below.')
    return uploaded_file


class ManualPaymentProofForm(forms.Form):
    screenshot = forms.FileField(help_text='Accepted formats: JPG, PNG, WEBP. Max 5 MB.')
    note = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Optional: mention the UPI app, time, or transaction context.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['screenshot'].widget.attrs.update({
            'class': 'form-control',
            'accept': 'image/png,image/jpeg,image/webp',
        })
        self.fields['note'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Optional note for the admin team',
        })

    def clean_screenshot(self):
        return validate_uploaded_image(self.cleaned_data['screenshot'])


class AdminPaymentReviewForm(forms.Form):
    payment_id = forms.IntegerField(widget=forms.HiddenInput)
    review_note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['review_note'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Optional internal/admin message',
        })


class AdminPaymentRejectForm(AdminPaymentReviewForm):
    review_note = forms.CharField(
        required=True,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

