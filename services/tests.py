from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile

from .models import Service, ServiceCategory


class ServicePublicPageTests(TestCase):
    def setUp(self):
        self.category = ServiceCategory.objects.create(name="Modular Furniture", slug="test-services")
        self.service = Service.objects.create(
            title="Kitchen Consultation",
            slug="kitchen-consultation",
            category=self.category,
            description="Planning and design consultation.",
            consultation_fee="499.00",
        )

    def test_services_landing_and_detail_pages_render(self):
        self.assertEqual(self.client.get(reverse("services_home")).status_code, 200)
        response = self.client.get(self.service.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kitchen Consultation")
        self.assertContains(response, "499.00")

    def test_booking_requires_customer_login(self):
        response = self.client.get(reverse("book_service", kwargs={"slug": self.service.slug}))
        self.assertEqual(response.status_code, 302)

    def admin_login(self):
        admin = get_user_model().objects.create_superuser("service-admin", "admin@example.com", "password")
        self.client.force_login(admin)

    def test_category_delete_is_post_only_and_blocks_dependencies(self):
        self.admin_login()
        delete_url = reverse("admin_service_category_delete", args=[self.category.id])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("admin_services"))
        self.assertTrue(ServiceCategory.objects.filter(pk=self.category.id).exists())

    def test_unused_parent_and_subcategory_can_be_deleted(self):
        self.admin_login()
        unused_parent = ServiceCategory.objects.create(name="Unused Parent", slug="unused-parent")
        unused_child = ServiceCategory.objects.create(name="Unused Child", slug="unused-child", parent=unused_parent)

        child_response = self.client.post(reverse("admin_service_category_delete", args=[unused_child.id]))
        self.assertRedirects(child_response, reverse("admin_services"))
        self.assertFalse(ServiceCategory.objects.filter(pk=unused_child.id).exists())

        parent_response = self.client.post(reverse("admin_service_category_delete", args=[unused_parent.id]))
        self.assertRedirects(parent_response, reverse("admin_services"))
        self.assertFalse(ServiceCategory.objects.filter(pk=unused_parent.id).exists())

    def test_employee_can_use_the_same_guarded_delete_endpoint(self):
        employee = get_user_model().objects.create_user("service-staff", password="password")
        UserProfile.objects.filter(user=employee).update(role=UserProfile.STAFF)
        self.client.force_login(employee)
        category = ServiceCategory.objects.create(name="Employee Category", slug="employee-category")
        response = self.client.post(reverse("employee_service_category_delete", args=[category.id]))
        self.assertRedirects(response, reverse("employee_services"))
        self.assertFalse(ServiceCategory.objects.filter(pk=category.id).exists())

    def test_category_count_is_direct_subcategory_count_on_both_dashboards(self):
        self.admin_login()
        child = ServiceCategory.objects.create(name="Kitchen", slug="count-kitchen", parent=self.category)
        response = self.client.get(reverse("admin_services"))
        self.assertContains(response, "1 subcategory")

        ServiceCategory.objects.create(name="Wardrobe", slug="count-wardrobe", parent=self.category)
        response = self.client.get(reverse("admin_services"))
        self.assertContains(response, "2 subcategories")

        self.client.post(reverse("admin_service_category_delete", args=[child.id]))
        response = self.client.get(reverse("admin_services"))
        self.assertContains(response, "1 subcategory")

        employee = get_user_model().objects.create_user("count-staff", password="password")
        UserProfile.objects.filter(user=employee).update(role=UserProfile.STAFF)
        self.client.force_login(employee)
        response = self.client.get(reverse("employee_services"))
        self.assertContains(response, "1 subcategory")
