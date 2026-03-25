from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.payments.models import Payment
from apps.projects.models import UserProject
from services.notification_service import NotificationService

try:
    import razorpay
except ImportError:
    razorpay = None


class PaymentService:
    def __init__(self):
        self.client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)) if razorpay and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET else None
        self.notifications = NotificationService()

    def list_user_payments(self, user):
        return Payment.objects.filter(user=user).select_related('user_project', 'user_project__project')

    @transaction.atomic
    def create_order(self, user, user_project_id, payment_type):
        user_project = UserProject.objects.select_related('project').get(pk=user_project_id, user=user)
        if user_project.status == UserProject.Status.REQUESTED:
            raise ValidationError('Project is not approved yet.')

        amount = self._resolve_amount(user_project, payment_type)
        payment = Payment.objects.create(user=user, user_project=user_project, amount=amount, type=payment_type)
        if not self.client:
            payment.razorpay_order_id = f'mock_order_{payment.id}'
            payment.save(update_fields=['razorpay_order_id'])
            return {'order_id': payment.razorpay_order_id, 'amount': int(amount * 100), 'currency': 'INR', 'payment_id': payment.id, 'mode': 'mock'}

        order = self.client.order.create({'amount': int(amount * 100), 'currency': 'INR', 'payment_capture': 1, 'notes': {'user_project_id': user_project.id, 'payment_type': payment_type}})
        payment.razorpay_order_id = order['id']
        payment.save(update_fields=['razorpay_order_id'])
        return {'order_id': order['id'], 'amount': order['amount'], 'currency': order['currency'], 'payment_id': payment.id, 'mode': 'live'}

    @transaction.atomic
    def verify_payment(self, user, payload):
        payment = Payment.objects.select_for_update().select_related('user_project', 'user_project__project').filter(
            user=user,
            user_project_id=payload['user_project_id'],
            razorpay_order_id=payload['order_id'],
            status=Payment.PaymentStatus.PENDING,
        ).first()
        if not payment:
            raise ValidationError('Payment record not found or already processed.')

        if self.client:
            self.client.utility.verify_payment_signature({
                'razorpay_order_id': payload['order_id'],
                'razorpay_payment_id': payload['payment_id'],
                'razorpay_signature': payload['signature'],
            })
        elif payload['signature'] != 'mock_signature':
            raise ValidationError('Invalid mock payment signature.')

        payment.razorpay_payment_id = payload['payment_id']
        payment.status = Payment.PaymentStatus.SUCCESS
        payment.save(update_fields=['razorpay_payment_id', 'status'])

        user_project = payment.user_project
        if payment.type == Payment.PaymentType.ADVANCE:
            user_project.status = UserProject.Status.IN_PROGRESS
        elif payment.type == Payment.PaymentType.FINAL and user_project.delivery_url:
            user_project.status = UserProject.Status.COMPLETED
        user_project.save(update_fields=['status', 'updated_at'])

        self.notifications.send_payment_confirmation(user.email, user_project.project.title, payment.amount, payment.type)
        return payment

    def _resolve_amount(self, user_project, payment_type):
        effective_price = Decimal(user_project.effective_price)
        if payment_type == Payment.PaymentType.ADVANCE:
            return (effective_price * Decimal('0.50')).quantize(Decimal('0.01'))
        final_paid = user_project.payments.filter(type=Payment.PaymentType.FINAL, status=Payment.PaymentStatus.SUCCESS).exists()
        if final_paid:
            raise ValidationError('Final payment already completed.')
        advance_paid = user_project.payments.filter(type=Payment.PaymentType.ADVANCE, status=Payment.PaymentStatus.SUCCESS).exists()
        if not advance_paid:
            raise ValidationError('Advance payment is required first.')
        return (effective_price * Decimal('0.50')).quantize(Decimal('0.01'))
