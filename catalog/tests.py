from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductReview


class ProductReviewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Boards & Panels", slug="boards-panels")
        self.product = Product.objects.create(
            name="Test Panel",
            slug="test-panel",
            sku="TEST-PANEL-1",
            category=self.category,
            price="299.00",
        )
        self.customer = get_user_model().objects.create_user(username="reviewer", password="test-password")
        self.product_url = reverse("product_detail", kwargs={"slug": self.product.slug})

    def test_logged_out_customer_can_read_reviews_but_not_submit(self):
        response = self.client.get(self.product_url)
        self.assertContains(response, "Sign in to leave a review.")
        self.assertNotContains(response, 'name="review"')

    def test_customer_can_create_then_update_one_review(self):
        self.client.force_login(self.customer)
        review_url = reverse("product_review", kwargs={"slug": self.product.slug})
        response = self.client.post(review_url, {"rating": "5", "review": "Excellent finish."})
        self.assertRedirects(response, f"{self.product_url}#reviews", fetch_redirect_response=False)
        self.assertEqual(ProductReview.objects.count(), 1)
        review = ProductReview.objects.get()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.customer, self.customer)

        response = self.client.post(review_url, {"rating": "4", "review": "Still a good product."})
        self.assertRedirects(response, f"{self.product_url}#reviews", fetch_redirect_response=False)
        self.assertEqual(ProductReview.objects.count(), 1)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)

    def test_invalid_review_stays_on_product_page(self):
        self.client.force_login(self.customer)
        review_url = reverse("product_review", kwargs={"slug": self.product.slug})
        response = self.client.post(review_url, {"rating": "6", "review": "No"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_shop_menu_reads_active_categories_from_database(self):
        main = Category.objects.create(name="Lighting Solutions", slug="lighting-solutions", sort_order=20)
        child = Category.objects.create(name="Pendant Lights", slug="pendant-lights", parent=main)

        response = self.client.get(reverse("home"))

        self.assertContains(response, main.name)
        self.assertContains(response, child.name)

    def test_category_seed_does_not_hide_custom_categories(self):
        custom = Category.objects.create(name="Lighting Solutions", slug="lighting-solutions", sort_order=20)

        call_command("seed_phoenix_categories")

        custom.refresh_from_db()
        self.assertTrue(custom.is_active)
        self.assertTrue(Category.objects.filter(slug="boards-panels", parent__isnull=True, is_active=True).exists())
