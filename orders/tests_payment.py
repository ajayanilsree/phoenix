from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from dashboard.forms import OrderStatusForm

from .models import Order


class RazorpayOrderStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="payment-state-user")
        self.order = Order.objects.create(
            order_number="PHX-STATE-1",
            customer=self.user,
            payment_method="razorpay",
            payment_status="pending",
            status=Order.CONFIRMED,
            grand_total=Decimal("250.00"),
        )

    def test_unpaid_razorpay_order_cannot_be_manually_confirmed(self):
        form = OrderStatusForm({"status": Order.CONFIRMED}, instance=self.order)
        self.assertFalse(form.is_valid())

    def test_paid_razorpay_order_can_be_confirmed(self):
        self.order.payment_status = "paid"
        form = OrderStatusForm({"status": Order.CONFIRMED}, instance=self.order)
        self.assertTrue(form.is_valid())
