from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from catalog.models import Category, Product
from catalog.models import ProductVariant


class StaffProductCreationTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username="staff-product", password="password")
        UserProfile.objects.filter(user=self.staff).update(role=UserProfile.STAFF)
        self.category = Category.objects.create(name="Staff Category", slug="staff-category")
        self.subcategory = Category.objects.create(name="Staff Subcategory", slug="staff-subcategory", parent=self.category)
        self.client.force_login(self.staff)

    def product_payload(self, **overrides):
        payload = {
            "name": "Staff Product",
            "sku": "STAFF-PRODUCT-1",
            "hsn_code": "9403",
            "category": self.category.id,
            "subcategory": self.subcategory.id,
            "full_description": "A staff-created product.",
            "unit_type": "piece",
            "size": "",
            "thickness": "",
            "colour": "",
            "finish": "",
            "features": "",
            "applications": "",
            "variant_type": Product.VARIANT_NONE,
            "variant_count": "1",
            "compare_at_price": "120.00",
            "price": "100.00",
            "promo_price": "95.00",
            "subpromo_price": "90.00",
            "agent_redeem_percentage": "0",
            "gst_rate": "18",
            "stock": "10",
            "low_stock_threshold": "5",
            "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "0",
            "variants-MIN_NUM_FORMS": "0",
            "variants-MAX_NUM_FORMS": "20",
        }
        payload.update(overrides)
        return payload

    def test_staff_can_create_simple_product(self):
        response = self.client.post(reverse("employee_product_add"), self.product_payload())
        self.assertRedirects(response, reverse("employee_products"))
        self.assertTrue(Product.objects.filter(sku="STAFF-PRODUCT-1").exists())

    def test_staff_can_create_size_variant_product(self):
        payload = self.product_payload(
            name="Staff Variant Product",
            sku="STAFF-VARIANT-1",
            size="Base",
            variant_type=Product.VARIANT_SIZE,
            **{
                "variants-0-name": "Large",
                "variants-0-description": "A large size option.",
                "variants-0-sku": "STAFF-VARIANT-1-L",
                "variants-0-hsn_code": "9403",
                "variants-0-size": "Large",
                "variants-0-thickness": "",
                "variants-0-colour": "",
                "variants-0-finish": "",
                "variants-0-unit_type": "piece",
                "variants-0-original_price": "150.00",
                "variants-0-selling_price": "125.00",
                "variants-0-promo_price": "120.00",
                "variants-0-subpromo_price": "110.00",
                "variants-0-agent_redeem_percentage": "10",
                "variants-0-gst_rate": "18",
                "variants-0-stock": "8",
                "variants-0-low_stock_threshold": "2",
            },
        )
        response = self.client.post(reverse("employee_product_add"), payload)
        self.assertRedirects(response, reverse("employee_products"))
        product = Product.objects.get(sku="STAFF-VARIANT-1")
        self.assertTrue(ProductVariant.objects.filter(product=product, sku="STAFF-VARIANT-1-L", size="Large").exists())

    def test_optional_base_attributes_and_images_can_be_empty(self):
        response = self.client.post(reverse("employee_product_add"), self.product_payload())
        self.assertRedirects(response, reverse("employee_products"))
        product = Product.objects.get(sku="STAFF-PRODUCT-1")
        self.assertEqual(product.size, "")
        self.assertFalse(product.images.exists())

    def test_missing_required_base_field_is_rejected(self):
        response = self.client.post(reverse("employee_product_add"), self.product_payload(name=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(Product.objects.filter(sku="STAFF-PRODUCT-1").exists())

    def test_ajax_validation_returns_field_and_variant_errors_without_redirect(self):
        payload = self.product_payload(hsn_code="")
        payload.update({
            "variant_type": Product.VARIANT_SIZE,
            "variant_count": "1",
            "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "0",
            "variants-0-name": "Option",
        })
        response = self.client.post(
            reverse("employee_product_add"),
            payload,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertTrue(any(error["label"] == "HSN Code" for error in data["errors"]))
        self.assertTrue(any(error["scope"] == "Variant 1" for error in data["errors"]))
        self.assertFalse(Product.objects.filter(sku="STAFF-PRODUCT-1").exists())

    def test_ajax_success_uses_added_message_and_redirect(self):
        response = self.client.post(
            reverse("employee_product_add"),
            self.product_payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Product added successfully.")
        self.assertEqual(response.json()["redirect"], reverse("employee_products"))
