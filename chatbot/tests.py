from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product


class ChatbotApiTests(TestCase):
    def post_message(self, message, **extra):
        return self.client.post(
            reverse("chatbot_message"),
            data={"message": message, **extra},
            content_type="application/json",
        )

    def test_empty_message_is_rejected(self):
        response = self.post_message("")
        self.assertEqual(response.status_code, 400)

    def test_too_long_message_is_rejected(self):
        with override_settings(CHATBOT_MAX_MESSAGE_LENGTH=5):
            response = self.post_message("too long")
        self.assertEqual(response.status_code, 400)

    @override_settings(CHATBOT_ENABLED=True, GEMINI_API_KEY="")
    def test_missing_api_key_uses_local_fallback(self):
        response = self.post_message("Show WPC boards")
        self.assertEqual(response.status_code, 200)
        self.assertIn("actions", response.json())

    def test_unrelated_question_is_redirected_without_gemini(self):
        with patch("chatbot.services.GeminiChatService.build_prompt") as build_prompt:
            response = self.post_message("What is the weather today?")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(build_prompt.called)

    def test_inactive_products_are_not_exposed(self):
        category = Category.objects.create(name="Boards & Panels", slug="boards-panels")
        Product.objects.create(
            name="Hidden WPC Board",
            slug="hidden-wpc-board",
            sku="HIDDEN-WPC",
            category=category,
            price="100.00",
            is_active=False,
        )
        response = self.post_message("Hidden WPC Board")
        self.assertNotContains(response, "Hidden WPC Board")

    def test_catalogue_product_match_returns_product_card(self):
        category = Category.objects.create(name="Boards & Panels", slug="boards-panels")
        Product.objects.create(
            name="WPC Foam Board",
            slug="wpc-foam-board",
            sku="WPC-1",
            category=category,
            short_description="WPC board for interiors",
            price="250.00",
            is_active=True,
        )
        response = self.post_message("WPC board")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["products"][0]["name"], "WPC Foam Board")
