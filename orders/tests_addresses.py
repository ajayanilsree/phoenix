from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from .forms import BillingAddressForm
from .models import Address, Order


class BillingAddressGstinTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="billing-customer", password="password")
        UserProfile.objects.filter(user=self.user).update(role=UserProfile.CUSTOMER)
        self.client.force_login(self.user)
        self.payload = {
            "full_name": "Billing Customer",
            "phone": "+919876543210",
            "line1": "10 Phoenix Street",
            "line2": "",
            "city": "Thiruvananthapuram",
            "district": "Thiruvananthapuram",
            "state": "Kerala",
            "postal_code": "695001",
            "country": "India",
            "gstin": "",
        }

    def test_gstin_is_optional_and_saved_uppercase(self):
        blank_form = BillingAddressForm(data=self.payload)
        self.assertTrue(blank_form.is_valid(), blank_form.errors)

        self.payload["gstin"] = "32abcde1234f1z5"
        response = self.client.post(reverse("customer_billing_address"), self.payload)
        self.assertRedirects(response, reverse("customer_billing_address"))
        address = Address.objects.get(user=self.user, address_type=Address.BILLING)
        self.assertEqual(address.gstin, "32ABCDE1234F1Z5")

    def test_invalid_gstin_is_rejected(self):
        self.payload["gstin"] = "not-valid"
        form = BillingAddressForm(data=self.payload)
        self.assertFalse(form.is_valid())
        self.assertIn("gstin", form.errors)

    def test_billing_edit_can_remove_gstin(self):
        address = Address.objects.create(user=self.user, address_type=Address.BILLING, is_default=True, gstin="32ABCDE1234F1Z5", **{key: value for key, value in self.payload.items() if key != "gstin"})
        self.payload["gstin"] = ""
        response = self.client.post(reverse("customer_billing_address"), self.payload)
        self.assertRedirects(response, reverse("customer_billing_address"))
        address.refresh_from_db()
        self.assertEqual(address.gstin, "")

    def test_order_gstin_snapshot_stays_stable_after_address_edit(self):
        address = Address.objects.create(user=self.user, address_type=Address.BILLING, is_default=True, gstin="32ABCDE1234F1Z5", **{key: value for key, value in self.payload.items() if key != "gstin"})
        order = Order.objects.create(order_number="PHX-GST-SNAPSHOT", customer=self.user, billing_address=address, billing_gstin=address.gstin)
        address.gstin = "29ABCDE1234F1Z5"
        address.save(update_fields=["gstin"])
        order.refresh_from_db()
        self.assertEqual(order.billing_gstin, "32ABCDE1234F1Z5")
