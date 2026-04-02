import logging

import requests
from django.conf import settings

from apps.projects.models import Notification

logger = logging.getLogger(__name__)


class NotificationDeliveryError(Exception):
    pass


class NotificationService:
    base_url = 'https://api.brevo.com/v3/smtp/email'

    def _sender(self):
        sender_email = (settings.BREVO_SENDER_EMAIL or '').strip()
        sender_name = (settings.BREVO_SENDER_NAME or 'ProjectHub').strip()
        if not sender_email:
            logger.error('Brevo email delivery skipped because BREVO_SENDER_EMAIL is not configured.')
            raise NotificationDeliveryError('Email service is not configured.')
        return {'name': sender_name, 'email': sender_email}

    def _post(self, payload):
        if not settings.BREVO_API_KEY:
            logger.error('Brevo email delivery skipped because BREVO_API_KEY is not configured.')
            raise NotificationDeliveryError('Email service is not configured.')
        headers = {
            'accept': 'application/json',
            'api-key': settings.BREVO_API_KEY,
            'content-type': 'application/json',
        }
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=10)
            logger.info(
                'Brevo API response received. Status=%s RecipientCount=%s Subject=%s',
                response.status_code,
                len(payload.get('to', [])),
                payload.get('subject'),
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            response_text = ''
            response_status = None
            if exc.response is not None:
                response_status = exc.response.status_code
                response_text = exc.response.text[:500]
            logger.exception('Brevo API request failed. Status=%s Body=%s', response_status, response_text)
            if response_status == 401:
                raise NotificationDeliveryError(
                    'Email service authorization failed. Check the Brevo API key and authorized IP settings.'
                ) from exc
            if response_status == 400:
                raise NotificationDeliveryError(
                    'Email service rejected the request. Check the sender configuration and payload.'
                ) from exc
            raise NotificationDeliveryError('Unable to send email at this time.') from exc

    def create_notification(self, *, user, title, message, notification_type, user_project=None, send_email=False):
        notification = Notification.objects.create(
            user=user,
            user_project=user_project,
            title=title,
            message=message,
            type=notification_type,
        )
        if send_email and user.email:
            payload = {
                'sender': self._sender(),
                'to': [{'email': user.email}],
                'subject': title,
                'htmlContent': f'<p>{message}</p>',
            }
            try:
                self._post(payload)
            except NotificationDeliveryError:
                logger.warning('Notification email delivery failed for user=%s title=%s', user.pk, title)
        return notification

    def send_otp(self, email, otp):
        payload = {
            'sender': self._sender(),
            'to': [{'email': email}],
            'subject': 'Your OTP Code',
            'htmlContent': f'<p>Your OTP is <strong>{otp}</strong>. It expires in 10 minutes.</p>',
        }
        return self._post(payload)

    def notify_project_approval(self, user_project):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title='Project approved',
            message=f'{user_project.project.title} has been approved with a total price of Rs. {user_project.total_price}.',
            notification_type=Notification.Type.APPROVAL,
            send_email=True,
        )

    def notify_payment_request(self, user_project, stage, amount):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title=f'Payment request for Stage {stage}',
            message=f'Please complete Stage {stage} payment of Rs. {amount} for {user_project.project.title} and upload your payment screenshot for verification.',
            notification_type=Notification.Type.PAYMENT,
            send_email=True,
        )

    def notify_payment_proof_uploaded(self, user_project, stage, amount):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title=f'Payment proof uploaded for Stage {stage}',
            message=f'Your payment proof for Rs. {amount} on {user_project.project.title} is under verification.',
            notification_type=Notification.Type.PAYMENT,
            send_email=True,
        )

    def notify_payment_success(self, user_project, stage, amount):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title=f'Stage {stage} payment received',
            message=f'Your Stage {stage} payment of Rs. {amount} for {user_project.project.title} has been verified.',
            notification_type=Notification.Type.PAYMENT,
            send_email=True,
        )

    def notify_payment_rejected(self, user_project, stage, reason):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title=f'Stage {stage} payment rejected',
            message=f'Your payment proof for {user_project.project.title} was rejected. Reason: {reason}',
            notification_type=Notification.Type.PAYMENT,
            send_email=True,
        )

    def notify_progress_update(self, user_project):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title='Project progress updated',
            message=f'{user_project.project.title} is now {user_project.progress}% complete.',
            notification_type=Notification.Type.PROGRESS,
        )

    def notify_stage_transition(self, user_project, label):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title='Project stage updated',
            message=f'{user_project.project.title} moved to {label}.',
            notification_type=Notification.Type.STAGE,
        )

    def notify_delivery(self, user_project):
        return self.create_notification(
            user=user_project.user,
            user_project=user_project,
            title='Project delivered',
            message=f'{user_project.project.title} has been delivered and is ready for download.',
            notification_type=Notification.Type.DELIVERY,
            send_email=True,
        )

    def notify_custom(self, *, user, title, message, user_project=None):
        return self.create_notification(
            user=user,
            user_project=user_project,
            title=title,
            message=message,
            notification_type=Notification.Type.SYSTEM,
        )
