from django import forms

from apps.payments.models import Payment


class PaymentRequestForm(forms.Form):
    user_project_id = forms.IntegerField(widget=forms.HiddenInput)
    payment_type = forms.ChoiceField(choices=Payment.PaymentType.choices)


class PaymentVerifyForm(forms.Form):
    user_project_id = forms.IntegerField()
    payment_id = forms.CharField(max_length=120)
    order_id = forms.CharField(max_length=120)
    signature = forms.CharField(max_length=255)
