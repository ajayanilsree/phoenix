from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product
from inventory.models import InventoryRecord

from .models import Cart, CartItem


class CartQuantityUpdateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cart-user", password="test-password")
        category = Category.objects.create(name="Boards & Panels", slug="boards-panels")
        self.product = Product.objects.create(
            name="Test Panel",
            slug="test-panel",
            sku="TEST-PANEL-1",
            category=category,
            price=Decimal("299.00"),
        )
        InventoryRecord.objects.create(product=self.product, current_stock=5)
        cart = Cart.objects.create(user=self.user)
        self.item = CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.url = reverse("update_cart_item", kwargs={"item_id": self.item.id})

    def test_quantity_update_returns_server_calculated_totals(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"quantity": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "success": True,
            "quantity": 2,
            "item_subtotal": "598.00",
            "cart_subtotal": "598.00",
            "cart_count": 2,
        })
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2)

    def test_quantity_above_stock_is_rejected_without_changing_cart(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"quantity": "6"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Only 5 units are available.", response.json()["message"])
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 1)

    def test_invalid_quantity_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"quantity": "0"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Quantity must be at least 1.")

    def test_subtotal_response_includes_all_cart_items(self):
        second = Product.objects.create(
            name="Second Panel",
            slug="second-panel",
            sku="SECOND-PANEL-1",
            category=self.product.category,
            price=Decimal("450.00"),
        )
        InventoryRecord.objects.create(product=second, current_stock=5)
        CartItem.objects.create(cart=self.item.cart, product=second, quantity=2)
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"quantity": "3"})

        self.assertEqual(response.json()["cart_subtotal"], "1797.00")
