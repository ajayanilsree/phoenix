from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


def validate_service_image(image):
    if image.size > 5 * 1024 * 1024:
        raise ValidationError("Service images must be 5MB or smaller.")


class ServiceCategory(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Service category"
        verbose_name_plural = "Service categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("service_category", kwargs={"slug": self.slug})


class Service(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    subcategory = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="subcategory_services", null=True, blank=True)
    description = models.TextField()
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def clean(self):
        super().clean()
        if self.consultation_fee is not None and self.consultation_fee < Decimal("0.00"):
            raise ValidationError({"consultation_fee": "Consultation fee cannot be negative."})
        if self.subcategory_id and self.subcategory.parent_id != self.category_id:
            raise ValidationError({"subcategory": "Choose a subcategory belonging to the selected category."})

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("service_detail", kwargs={"slug": self.slug})


class ServiceImage(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="services/", validators=[validate_service_image])
    alt_text = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class ServiceLinkPreview(models.Model):
    url = models.URLField(max_length=2048, unique=True)
    title = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=2048, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class ServiceBooking(models.Model):
    PENDING = "pending"
    COMPLETED = "completed"
    SERVICE_STATUS_CHOICES = [(PENDING, "Pending"), (COMPLETED, "Completed")]
    PAYMENT_PENDING = "pending"
    PAYMENT_CONFIRMED = "confirmed"
    PAYMENT_FAILED = "failed"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_STATUS_CHOICES = [(PAYMENT_PENDING, "Pending Payment"), (PAYMENT_CONFIRMED, "Payment Confirmed"), (PAYMENT_FAILED, "Failed"), (PAYMENT_REFUNDED, "Refunded")]

    booking_reference = models.CharField(max_length=32, unique=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    service_title_snapshot = models.CharField(max_length=180)
    consultation_fee_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="service_bookings")
    customer_name = models.CharField(max_length=140)
    customer_email = models.EmailField()
    customer_mobile = models.CharField(max_length=30)
    requirements = models.TextField(blank=True)
    service_status = models.CharField(max_length=20, choices=SERVICE_STATUS_CHOICES, default=PENDING)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    razorpay_order_id = models.CharField(max_length=80, blank=True)
    razorpay_payment_id = models.CharField(max_length=80, blank=True)
    razorpay_signature = models.CharField(max_length=160, blank=True)
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.booking_reference
