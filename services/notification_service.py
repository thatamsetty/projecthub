import requests
from django.conf import settings


class NotificationService:
    base_url = 'https://api.brevo.com/v3/smtp/email'

    def _post(self, payload):
        if not settings.BREVO_API_KEY:
            return {'skipped': True, 'reason': 'BREVO_API_KEY not configured'}
        headers = {
            'accept': 'application/json',
            'api-key': settings.BREVO_API_KEY,
            'content-type': 'application/json',
        }
        response = requests.post(self.base_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def send_otp(self, email, otp):
        payload = {
            'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
            'to': [{'email': email}],
            'subject': 'Your ProjectHub OTP',
            'htmlContent': f'<p>Your OTP is <strong>{otp}</strong>. It expires in 10 minutes.</p>',
        }
        return self._post(payload)

    def send_project_approval(self, email, project_title, amount):
        payload = {
            'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
            'to': [{'email': email}],
            'subject': 'Project Approved',
            'htmlContent': f'<p>{project_title} was approved. Agreed amount: Rs. {amount}</p>',
        }
        return self._post(payload)

    def send_payment_confirmation(self, email, project_title, amount, payment_type):
        payload = {
            'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
            'to': [{'email': email}],
            'subject': 'Payment Confirmed',
            'htmlContent': f'<p>{payment_type} payment of Rs. {amount} for {project_title} has been confirmed.</p>',
        }
        return self._post(payload)

    def send_progress_update(self, email, project_title, progress):
        payload = {
            'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
            'to': [{'email': email}],
            'subject': 'Project Progress Updated',
            'htmlContent': f'<p>{project_title} is now {progress}% complete.</p>',
        }
        return self._post(payload)
