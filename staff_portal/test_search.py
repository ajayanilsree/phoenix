from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from catalog.models import Category, Product, ProductVariant


class EmployeeProductSearchTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user(username="search-employee", password="password")
        UserProfile.objects.filter(user=self.employee).update(role=UserProfile.STAFF)
        self.client.force_login(self.employee)
        self.category = Category.objects.create(name="Others", slug="employee-others")
        self.product = Product.objects.create(
            name="SS-10",
            slug="employee-ss-10",
            sku="PHX003",
            category=self.category,
            price="50.00",
            has_variants=True,
        )
        ProductVariant.objects.create(product=self.product, name="Small", sku="PHX004", selling_price="50.00", stock=2)

    def test_employee_product_search_matches_variant_sku(self):
        response = self.client.get(reverse("employee_products"), {"q": "PHX004"})

        products = list(response.context["page_obj"].object_list)
        self.assertEqual([item.pk for item in products], [self.product.pk])
        self.assertContains(response, "SS-10")
