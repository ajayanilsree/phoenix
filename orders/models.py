from decimal import Decimal

from django.conf import settings
from django.db import models


class Address(models.Model):
    BILLING = "billing"
    DELIVERY = "delivery"
    ADDRESS_TYPE_CHOICES = [(BILLING, "Billing"), (DELIVERY, "Delivery")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=12, choices=ADDRESS_TYPE_CHOICES, default=BILLING)
    full_name = models.CharField(max_length=140)
    phone = models.CharField(max_length=24)
    line1 = models.CharField(max_length=180)
    line2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=80, default="India")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.full_name}, {self.city}"


class Order(models.Model):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    PACKED = "packed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (PROCESSING, "Processing"),
        (PACKED, "Packed"),
        (SHIPPED, "Shipped"),
        (DELIVERED, "Delivered"),
        (CANCELLED, "Cancelled"),
    ]

    PAYMENT_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("razorpay", "Razorpay"),
    ]

    order_number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="agent_orders", blank=True, null=True)
    agent_code_snapshot = models.CharField(max_length=20, blank=True)
    agent_discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    agent_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal_before_agent_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_address = models.ForeignKey(Address, on_delete=models.PROTECT, blank=True, null=True)
    billing_address = models.ForeignKey(Address, on_delete=models.PROTECT, blank=True, null=True, related_name="billed_orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="pending")
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default="razorpay")
    razorpay_order_id = models.CharField(max_length=80, blank=True)
    razorpay_payment_id = models.CharField(max_length=80, blank=True)
    razorpay_signature = models.CharField(max_length=160, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    business_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    def recalculate_totals(self):
        self.subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        if not self.subtotal_before_agent_discount:
            self.subtotal_before_agent_discount = self.subtotal
        self.grand_total = self.subtotal + self.delivery_charge + self.tax_total - self.discount_total


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, blank=True, null=True)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.SET_NULL, blank=True, null=True)
    product_name = models.CharField(max_length=180)
    sku = models.CharField(max_length=80)
    selected_variant = models.CharField(max_length=160, blank=True)
    unit_type = models.CharField(max_length=30)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return self.product_name


class PaymentRecord(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=80, default="manual")
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=40, default="pending")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
