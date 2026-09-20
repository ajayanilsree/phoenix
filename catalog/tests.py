from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductImage, ProductReview, ProductVariant


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

    def test_public_pages_include_floating_whatsapp_contact(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "https://wa.me/917306430531")
        self.assertContains(response, "Contact Phoenix Interior Hub on WhatsApp")

    def test_category_seed_does_not_hide_custom_categories(self):
        custom = Category.objects.create(name="Lighting Solutions", slug="lighting-solutions", sort_order=20)

        call_command("seed_phoenix_categories")

        custom.refresh_from_db()
        self.assertTrue(custom.is_active)
        self.assertTrue(Category.objects.filter(slug="boards-panels", parent__isnull=True, is_active=True).exists())

    def test_product_card_renders_a_clean_dynamic_discount_badge(self):
        discounted = Product.objects.create(
            name="Discounted Panel",
            slug="discounted-panel",
            sku="DISCOUNTED-PANEL-1",
            category=self.category,
            price="300.00",
            compare_at_price="500.00",
        )

        response = self.client.get(reverse("shop"))

        self.assertContains(response, 'class="product-discount-badge">40% OFF</span>')
        self.assertNotContains(response, "-40%")
        discounted.refresh_from_db()
        self.assertEqual(discounted.discount_percent, 40)

    def test_variant_product_choose_options_links_to_product_detail(self):
        product = Product.objects.create(
            name="Variant Panel",
            slug="variant-panel",
            sku="VARIANT-PANEL-1",
            category=self.category,
            price="500.00",
            has_variants=True,
        )
        ProductVariant.objects.create(
            product=product,
            name="Large",
            sku="VARIANT-PANEL-1-L",
            selling_price="500.00",
            stock=5,
        )

        response = self.client.get(reverse("shop"))

        product_url = reverse("product_detail", kwargs={"slug": product.slug})
        self.assertContains(response, f'href="{product_url}">Choose Options</a>')
        self.assertNotContains(response, 'type="submit" disabled>Choose Options')

    def test_shop_pagination_preserves_filters_and_exposes_public_share_urls(self):
        for index in range(12):
            Product.objects.create(
                name=f"Test Panel {index + 2}",
                slug=f"test-panel-{index + 2}",
                sku=f"TEST-PANEL-{index + 2}",
                category=self.category,
                price="299.00",
            )

        response = self.client.get(reverse("shop"), {"q": "Test", "sort": "name", "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")
        self.assertContains(response, 'data-product-url="https://www.phoenixinteriorhub.com/product/')
        page_two = next(item for item in response.context["pagination_items"] if item.get("number") == 2)
        self.assertIn("page=2", page_two["url"])
        self.assertIn("q=Test", page_two["url"])
        self.assertIn("sort=name", page_two["url"])
        self.assertNotIn("127.0.0.1", page_two["url"])

    def test_product_detail_share_url_is_public_and_uses_parent_product(self):
        ProductImage.objects.create(
            product=self.product,
            image="products/test.png",
            is_primary=True,
        )
        response = self.client.get(self.product_url)
        self.assertContains(response, 'data-product-url="https://www.phoenixinteriorhub.com/product/test-panel/"')
        self.assertContains(response, 'aria-label="Share Test Panel"')
