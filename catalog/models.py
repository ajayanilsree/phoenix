from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
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
        return self.images.filter(is_primary=True).first() or self.images.first()

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


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
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
        existing = ProductImage.objects.filter(product=self.product)
        if self.pk:
            existing = existing.exclude(pk=self.pk)
        if self.product_id and existing.count() >= 4:
            raise ValidationError("A product can have a maximum of 4 images.")


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    size = models.CharField(max_length=80, blank=True)
    thickness = models.CharField(max_length=80, blank=True)
    colour = models.CharField(max_length=80, blank=True)
    finish = models.CharField(max_length=100, blank=True)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product__name", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def price(self):
        return self.product.price + self.price_delta


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=80)
    value = models.CharField(max_length=180)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.product.name}: {self.name}"
