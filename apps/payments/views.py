from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from apps.payments.forms import ManualPaymentProofForm
from services.payment_service import PaymentService


@login_required
def payments_view(request):
    payment_rows = PaymentService().list_user_payments(request.user)
    return render(request, 'user/payments.html', {'payment_rows': payment_rows})


@login_required
def manual_payment_view(request, user_project_id, stage):
    service = PaymentService()
    try:
        context = service.get_manual_payment_context(request.user, user_project_id, stage)
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect('/payments/')

    form = ManualPaymentProofForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if not context['can_upload_proof']:
            messages.info(request, 'Payment proof is already submitted for this stage.')
            return redirect(request.path)
        if form.is_valid():
            try:
                service.submit_manual_payment_proof(
                    request.user,
                    user_project_id,
                    stage,
                    form.cleaned_data['screenshot'],
                    form.cleaned_data.get('note', ''),
                )
                messages.success(request, 'Payment screenshot uploaded successfully. Our team will verify it shortly.')
                return redirect(request.path)
            except ValidationError as exc:
                form.add_error(None, exc.message)

    context['form'] = form
    return render(request, 'user/payment_qr.html', context)
