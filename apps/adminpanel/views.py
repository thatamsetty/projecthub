from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.adminpanel.decorators import staff_required
from apps.adminpanel.forms import AdminLoginForm
from apps.payments.forms import AdminPaymentRejectForm, AdminPaymentReviewForm
from apps.projects.forms import (
    ManualNotificationForm,
    ProjectApprovalForm,
    ProjectCatalogForm,
    ProjectDeliveryForm,
    ProjectProgressForm,
)
from apps.projects.models import ProjectCatalog, UserProject
from services.admin_service import AdminService
from services.payment_service import PaymentService
from services.user_service import UserAuthService


def admin_login_view(request):
    form = AdminLoginForm(request, data=request.POST or None)
    auth_service = UserAuthService()
    if request.method == 'POST' and form.is_valid():
        user = auth_service.login(request, form.cleaned_data['username'], form.cleaned_data['password'])
        if user and user.is_staff:
            return redirect('/admin-dashboard/')
        if user and not user.is_staff:
            auth_service.set_online_status(user, False)
            logout(request)
        form.add_error(None, 'Staff access required.')
    return render(request, 'admin/login.html', {'form': form})


@staff_required
def admin_dashboard_view(request):
    context = AdminService(actor=request.user).dashboard_summary()
    return render(request, 'admin/dashboard.html', context)


@staff_required
def admin_projects_view(request):
    form = ProjectCatalogForm(request.POST or None)
    context = AdminService(actor=request.user).list_project_catalog_context()
    if request.method == 'POST' and form.is_valid():
        try:
            AdminService(actor=request.user).create_catalog_item(form.cleaned_data)
            return redirect('/admin/projects/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    context['form'] = form
    return render(request, 'admin/projects.html', context)


@staff_required
def admin_project_edit_view(request, project_id):
    project = get_object_or_404(ProjectCatalog, pk=project_id)
    form = ProjectCatalogForm(request.POST or None, instance=project)
    if request.method == 'POST' and form.is_valid():
        try:
            AdminService(actor=request.user).update_catalog_item(project, form.cleaned_data)
            return redirect('/admin/projects/')
        except ValidationError as exc:
            form.add_error(None, exc.message)
    return render(request, 'admin/project_edit.html', {'form': form, 'project': project})


@staff_required
def admin_users_view(request):
    return render(request, 'admin/users.html', AdminService(actor=request.user).list_users_context())


@staff_required
def admin_payments_view(request):
    context = AdminService(actor=request.user).payment_users_context(
        search=request.GET.get('q', ''),
        payment_filter=request.GET.get('filter', 'all'),
    )
    return render(request, 'admin/payments.html', context)


@staff_required
def admin_payment_user_detail_view(request, user_id):
    context = AdminService(actor=request.user).payment_user_projects_context(user_id)
    return render(request, 'admin/payment_user_detail.html', context)


@staff_required
def admin_project_payment_detail_view(request, user_project_id):
    service = PaymentService(actor=request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'approve_payment':
                approve_form = AdminPaymentReviewForm(request.POST)
                if approve_form.is_valid():
                    service.approve_manual_payment(
                        approve_form.cleaned_data['payment_id'],
                        approve_form.cleaned_data.get('review_note', ''),
                    )
                    messages.success(request, 'Payment approved successfully.')
                    return redirect(request.path)
            elif action == 'reject_payment':
                reject_form = AdminPaymentRejectForm(request.POST)
                if reject_form.is_valid():
                    service.reject_manual_payment(
                        reject_form.cleaned_data['payment_id'],
                        reject_form.cleaned_data['review_note'],
                    )
                    messages.success(request, 'Payment rejected and stage reopened.')
                    return redirect(request.path)
            elif action == 'send_reminder':
                payment_id = int(request.POST.get('payment_id'))
                service.send_payment_reminder(payment_id, request.POST.get('review_note', ''))
                messages.success(request, 'Payment reminder sent to the user.')
                return redirect(request.path)
            elif action == 'auto_reminder':
                user_project = get_object_or_404(UserProject, pk=user_project_id)
                reminded = service.trigger_auto_reminders_for_project(user_project)
                if reminded:
                    messages.success(request, f'Auto reminders sent for {reminded} overdue payment(s).')
                else:
                    messages.info(request, 'No overdue payments found for auto reminders.')
                return redirect(request.path)
        except (ValidationError, ValueError) as exc:
            messages.error(request, str(exc))

    context = AdminService(actor=request.user).payment_project_detail_context(user_project_id)
    context['approve_form'] = AdminPaymentReviewForm()
    context['reject_form'] = AdminPaymentRejectForm()
    return render(request, 'admin/payment_project_detail.html', context)


@staff_required
def admin_project_payment_invoice_view(request, user_project_id):
    context = AdminService(actor=request.user).payment_project_detail_context(user_project_id)
    user_project = context['user_project']
    issued_at = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        'ProjectHub Invoice',
        f'Generated At: {issued_at}',
        f'Client: {user_project.user.username} ({user_project.user.email})',
        f'Project: {user_project.project.title}',
        f'Total Amount: Rs. {context["total_amount"]}',
        f'Paid Amount: Rs. {context["paid_amount"]}',
        f'Pending Amount: Rs. {context["pending_amount"]}',
        '',
        'Milestones:',
    ]
    for row in context['stage_rows']:
        lines.append(f'- {row["label"]}: Rs. {row["amount"]} [{row["status_label"]}]')
    payload = '\n'.join(lines)
    response = HttpResponse(payload, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="invoice-project-{user_project.id}.txt"'
    return response


@staff_required
def admin_user_project_edit_view(request, user_project_id):
    user_project = get_object_or_404(UserProject.objects.select_related('user', 'project').prefetch_related('payments', 'notifications', 'audit_logs'), pk=user_project_id)
    service = AdminService(actor=request.user)

    approval_form = ProjectApprovalForm(prefix='approval', initial={
        'total_price': user_project.total_price or user_project.project.base_price or '',
        'installment_1_percentage': 30,
        'installment_2_percentage': 40,
        'installment_3_percentage': 30,
    })
    progress_form = ProjectProgressForm(prefix='progress', initial={'progress': user_project.progress, 'admin_notes': user_project.admin_notes})
    delivery_form = ProjectDeliveryForm(prefix='delivery', initial={'delivery_url': user_project.delivery_url, 'admin_notes': user_project.admin_notes})
    notification_form = ManualNotificationForm(prefix='notify')
    approve_payment_form = AdminPaymentReviewForm()
    reject_payment_form = AdminPaymentRejectForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'approve':
                approval_form = ProjectApprovalForm(request.POST, prefix='approval')
                if approval_form.is_valid():
                    percentages = [
                        approval_form.cleaned_data['installment_1_percentage'],
                        approval_form.cleaned_data['installment_2_percentage'],
                        approval_form.cleaned_data['installment_3_percentage'],
                    ]
                    service.approve_project(user_project, approval_form.cleaned_data['total_price'], percentages)
                    return redirect(request.path)
            elif action == 'progress':
                progress_form = ProjectProgressForm(request.POST, prefix='progress')
                if progress_form.is_valid():
                    service.update_progress(user_project, progress_form.cleaned_data['progress'], progress_form.cleaned_data['admin_notes'])
                    return redirect(request.path)
            elif action == 'deliver':
                delivery_form = ProjectDeliveryForm(request.POST, request.FILES, prefix='delivery')
                if delivery_form.is_valid():
                    service.deliver_project(
                        user_project,
                        delivery_file=request.FILES.get('delivery-delivery_file'),
                        delivery_url=delivery_form.cleaned_data['delivery_url'],
                        admin_notes=delivery_form.cleaned_data['admin_notes'],
                    )
                    return redirect(request.path)
            elif action == 'notify':
                notification_form = ManualNotificationForm(request.POST, prefix='notify')
                if notification_form.is_valid():
                    service.send_manual_notification(user_project, notification_form.cleaned_data['title'], notification_form.cleaned_data['message'])
                    return redirect(request.path)
            elif action == 'approve_payment':
                approve_payment_form = AdminPaymentReviewForm(request.POST)
                if approve_payment_form.is_valid():
                    PaymentService(actor=request.user).approve_manual_payment(
                        approve_payment_form.cleaned_data['payment_id'],
                        approve_payment_form.cleaned_data.get('review_note', ''),
                    )
                    return redirect(request.path)
            elif action == 'reject_payment':
                reject_payment_form = AdminPaymentRejectForm(request.POST)
                if reject_payment_form.is_valid():
                    PaymentService(actor=request.user).reject_manual_payment(
                        reject_payment_form.cleaned_data['payment_id'],
                        reject_payment_form.cleaned_data['review_note'],
                    )
                    return redirect(request.path)
        except ValidationError as exc:
            if action == 'approve':
                approval_form.add_error(None, exc.message)
            elif action == 'progress':
                progress_form.add_error(None, exc.message)
            elif action == 'deliver':
                delivery_form.add_error(None, exc.message)
            elif action == 'notify':
                notification_form.add_error(None, exc.message)
            elif action == 'approve_payment':
                approve_payment_form.add_error(None, exc.message)
            elif action == 'reject_payment':
                reject_payment_form.add_error(None, exc.message)

    return render(request, 'admin/user_project_edit.html', {
        'user_project': user_project,
        'approval_form': approval_form,
        'progress_form': progress_form,
        'delivery_form': delivery_form,
        'notification_form': notification_form,
        'approve_payment_form': approve_payment_form,
        'reject_payment_form': reject_payment_form,
    })
