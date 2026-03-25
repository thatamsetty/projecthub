from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.payments.forms import PaymentRequestForm, PaymentVerifyForm
from services.payment_service import PaymentService


@login_required
def payments_view(request):
    payment_rows = PaymentService().list_user_payments(request.user)
    return render(request, 'user/payments.html', {'payment_rows': payment_rows, 'razorpay_key_id': settings.RAZORPAY_KEY_ID})


@login_required
@require_POST
def create_payment_order_view(request):
    form = PaymentRequestForm(request.POST)
    if form.is_valid():
        try:
            order_data = PaymentService().create_order(request.user, form.cleaned_data['user_project_id'], form.cleaned_data['payment_type'])
            return JsonResponse(order_data)
        except ValidationError as exc:
            return JsonResponse({'error': exc.message}, status=400)
    return JsonResponse({'errors': form.errors}, status=400)


@login_required
@require_POST
def verify_payment_view(request):
    form = PaymentVerifyForm(request.POST)
    if form.is_valid():
        try:
            PaymentService().verify_payment(request.user, form.cleaned_data)
            return JsonResponse({'status': 'verified'})
        except ValidationError as exc:
            return JsonResponse({'error': exc.message}, status=400)
    return JsonResponse({'errors': form.errors}, status=400)
