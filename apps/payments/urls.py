from django.urls import path

from apps.payments.views import create_payment_order_view, payments_view, verify_payment_view

urlpatterns = [
    path('payments/', payments_view, name='payments'),
    path('payments/create-order/', create_payment_order_view, name='create_payment_order'),
    path('payments/verify/', verify_payment_view, name='verify_payment'),
]
