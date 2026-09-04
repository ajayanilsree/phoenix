from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.urls import reverse


def validate_product_image_size(image):
    max_size = 5 * 1024 * 1024
    if image.size > max_size:
        raise ValidationError("Product images must be 5MB or smaller.")


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="children", blank=True, null=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("category_detail", kwargs={"slug": self.slug})


class Product(models.Model):
    VARIANT_NONE = "none"
    VARIANT_SIZE = "size"
    VARIANT_COLOR = "color"
    VARIANT_TYPE_CHOICES = [(VARIANT_NONE, "None"), (VARIANT_SIZE, "Size"), (VARIANT_COLOR, "Color")]
    UNIT_CHOICES = [
        ("piece", "Piece"),
        ("sheet", "Sheet"),
        ("panel", "Panel"),
        ("board", "Board"),
        ("box", "Box"),
        ("set", "Set"),
        ("running_foot", "Running Foot"),
        ("square_foot", "Square Foot"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=80, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    subcategory = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="subcategory_products", blank=True, null=True)
    short_description = models.CharField(max_length=240, blank=True)
    full_description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    unit_type = models.CharField(max_length=30, choices=UNIT_CHOICES, default="piece")
    size = models.CharField(max_length=80, blank=True)
    thickness = models.CharField(max_length=80, blank=True)
    colour = models.CharField(max_length=80, blank=True)
    finish = models.CharField(max_length=100, blank=True)
    pattern = models.CharField(max_length=100, blank=True)
    texture = models.CharField(max_length=100, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    features = models.TextField(blank=True)
    applications = models.TextField(blank=True)
    has_variants = models.BooleanField(default=False)
    variant_type = models.CharField(max_length=12, choices=VARIANT_TYPE_CHOICES, default=VARIANT_NONE)
    installation_notes = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    featured_order = models.PositiveIntegerField(default=0)
    is_trending = models.BooleanField(default=False)
    trending_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"slug": self.slug})

    def clean(self):
        super().clean()
        if self.price is not None and self.price < Decimal("0.00"):
            raise ValidationError({"price": "Discount/selling price cannot be negative."})
        if self.compare_at_price is not None:
            if self.compare_at_price <= Decimal("0.00"):
                raise ValidationError({"compare_at_price": "Original price must be greater than zero."})
            if self.price is not None and self.compare_at_price < self.price:
                raise ValidationError({"compare_at_price": "Original price should be greater than or equal to selling price."})

    @property
    def primary_image(self):
        base_images = self.images.filter(variant__isnull=True)
        return base_images.filter(is_primary=True).first() or base_images.first()

    @property
    def original_price(self):
        return self.compare_at_price

    @property
    def selling_price(self):
        return self.price

    @property
    def has_discount(self):
        return self.compare_at_price and self.compare_at_price > self.price

    @property
    def discount_percent(self):
        if not self.has_discount:
            return None
        return round(((self.compare_at_price - self.price) / self.compare_at_price) * 100)

    @property
    def display_price(self):
        prices = [variant.price for variant in self.variants.filter(is_active=True)]
        if prices and min(prices) != max(prices):
            return f"From ₹{min(prices)}"
        return f"₹{prices[0] if prices else self.price}"

    @property
    def total_variant_stock(self):
        return sum(variant.stock for variant in self.variants.filter(is_active=True))


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    variant = models.ForeignKey("ProductVariant", on_delete=models.CASCADE, related_name="images", blank=True, null=True)
    image = models.ImageField(
        upload_to="products/",
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"]),
            validate_product_image_size,
        ],
    )
    alt_text = models.CharField(max_length=160, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.alt_text or self.product.name

    def clean(self):
        super().clean()
        if not self.product_id:
            return
        existing = ProductImage.objects.filter(product=self.product, variant=self.variant)
        if self.pk:
            existing = existing.exclude(pk=self.pk)
        if self.product_id and existing.count() >= 4:
            raise ValidationError("A product can have a maximum of 4 images.")


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    variant_type = models.CharField(max_length=12, choices=Product.VARIANT_TYPE_CHOICES, default=Product.VARIANT_NONE)
    sku = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    size = models.CharField(max_length=80, blank=True)
    unit_type = models.CharField(max_length=30, choices=Product.UNIT_CHOICES, blank=True)
    thickness = models.CharField(max_length=80, blank=True)
    colour = models.CharField(max_length=80, blank=True)
    finish = models.CharField(max_length=100, blank=True)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def price(self):
        return self.selling_price if self.selling_price is not None else self.product.price + self.price_delta

    @property
    def compare_price(self):
        return self.original_price if self.original_price is not None else self.product.compare_at_price

    @property
    def has_discount(self):
        return bool(self.compare_price and self.compare_price > self.price)

    @property
    def discount_percent(self):
        if not self.has_discount:
            return None
        return round(((self.compare_price - self.price) / self.compare_price) * 100)

    def clean(self):
        super().clean()
        if self.selling_price is not None and self.selling_price < 0:
            raise ValidationError({"selling_price": "Selling price cannot be negative."})
        if self.original_price is not None and self.original_price < 0:
            raise ValidationError({"original_price": "Original price cannot be negative."})
        if self.original_price is not None and self.selling_price is not None and self.selling_price > self.original_price:
            raise ValidationError({"selling_price": "Selling price must be less than or equal to original price."})


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=80)
    value = models.CharField(max_length=180)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.product.name}: {self.name}"


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reviews")
    rating = models.PositiveSmallIntegerField()
    review = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "customer"],
                name="unique_customer_product_review",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} review by {self.customer}"
