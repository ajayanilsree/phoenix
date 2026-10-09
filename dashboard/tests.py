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


class AdminCategoryDeletionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="category-admin",
            email="category-admin@example.com",
            password="password",
        )
        self.client.force_login(self.admin)

    def test_delete_controls_render_and_endpoints_require_post(self):
        parent = Category.objects.create(name="Delete Parent", slug="delete-parent")
        child = Category.objects.create(name="Delete Child", slug="delete-child", parent=parent)
        response = self.client.get(reverse("admin_categories"))
        self.assertContains(response, "Delete Category")
        self.assertContains(response, "Delete Subcategory")
        self.assertEqual(self.client.get(reverse("admin_category_delete", args=[parent.id])).status_code, 405)
        self.assertEqual(self.client.get(reverse("admin_subcategory_delete", args=[parent.id, child.id])).status_code, 405)

    def test_parent_and_subcategory_dependencies_block_deletion(self):
        parent = Category.objects.create(name="Protected Parent", slug="protected-parent")
        child = Category.objects.create(name="Protected Child", slug="protected-child", parent=parent)
        Product.objects.create(name="Protected Product", slug="protected-product", sku="PROTECTED-1", category=parent, subcategory=child, price="10.00")
        self.client.post(reverse("admin_category_delete", args=[parent.id]))
        self.assertTrue(Category.objects.filter(pk=parent.id).exists())
        self.client.post(reverse("admin_subcategory_delete", args=[parent.id, child.id]))
        self.assertTrue(Category.objects.filter(pk=child.id).exists())

    def test_unused_parent_and_subcategory_can_be_deleted(self):
        parent = Category.objects.create(name="Unused Parent", slug="unused-parent")
        child = Category.objects.create(name="Unused Child", slug="unused-child", parent=parent)
        self.client.post(reverse("admin_subcategory_delete", args=[parent.id, child.id]))
        self.assertFalse(Category.objects.filter(pk=child.id).exists())
        self.client.post(reverse("admin_category_delete", args=[parent.id]))
        self.assertFalse(Category.objects.filter(pk=parent.id).exists())
