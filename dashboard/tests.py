from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from catalog.models import Category, Product, ProductVariant


class AdminProductSearchTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="search-admin",
            email="search-admin@example.com",
            password="password",
        )
        self.client.force_login(self.admin)
        self.category = Category.objects.create(name="Others", slug="others")
        self.product = Product.objects.create(
            name="SS-10",
            slug="admin-ss-10",
            sku="PHX003",
            category=self.category,
            price="50.00",
            has_variants=True,
        )
        ProductVariant.objects.create(product=self.product, name="Small", sku="PHX004", selling_price="50.00", stock=2)

    def test_admin_product_search_matches_variant_sku_case_and_whitespace_insensitively(self):
        response = self.client.get(reverse("admin_products"), {"q": "  phx004  "})

        products = list(response.context["page_obj"].object_list)
        self.assertEqual([item.pk for item in products], [self.product.pk])
        self.assertContains(response, "SS-10")
