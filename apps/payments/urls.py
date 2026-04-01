from django.urls import path

from apps.payments.views import manual_payment_view, payments_view

urlpatterns = [
    path('payments/', payments_view, name='payments'),
    path('payments/<int:user_project_id>/stage/<int:stage>/', manual_payment_view, name='manual_payment'),
]
