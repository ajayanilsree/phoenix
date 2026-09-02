import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetOtpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="phoenix-customer",
            email="customer@example.com",
            password="OldStrongPassword123!",
        )

    def request_reset(self):
        return self.client.post(
            reverse("forgot_password"),
            {"username": self.user.username, "email": self.user.email},
        )

    def test_unknown_account_gets_generic_response_without_email(self):
        response = self.client.post(
            reverse("forgot_password"),
            {"username": "missing-customer", "email": "missing@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If the details match an account")
        self.assertEqual(len(mail.outbox), 0)

    def test_customer_can_verify_otp_and_set_new_password(self):
        response = self.request_reset()
        self.assertRedirects(response, reverse("verify_otp"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)

        otp = re.search(r"\b\d{6}\b", mail.outbox[0].body).group()
        response = self.client.post(reverse("verify_otp"), {"otp": otp})
        self.assertRedirects(response, reverse("reset_password"), fetch_redirect_response=False)

        response = self.client.post(
            reverse("reset_password"),
            {
                "new_password1": "NewStrongPassword123!",
                "new_password2": "NewStrongPassword123!",
            },
        )
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))
        self.assertFalse(self.user.check_password("OldStrongPassword123!"))

    def test_wrong_otp_does_not_change_password(self):
        self.request_reset()
        response = self.client.post(reverse("verify_otp"), {"otp": "000000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "verification code is incorrect")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldStrongPassword123!"))
