from django.conf import settings
from django.db import models


class InventoryRecord(models.Model):
    product = models.OneToOneField("catalog.Product", on_delete=models.CASCADE, related_name="inventory")
    variant = models.OneToOneField("catalog.ProductVariant", on_delete=models.CASCADE, related_name="inventory", blank=True, null=True)
    current_stock = models.IntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name"]

    @property
    def stock_status(self):
        if self.current_stock <= 0:
            return "out_of_stock"
        if self.current_stock <= self.low_stock_threshold:
            return "low_stock"
        return "in_stock"

    def __str__(self):
        return f"{self.product.sku}: {self.current_stock}"


class StockMovement(models.Model):
    ADJUSTMENT = "adjustment"
    SALE = "sale"
    RETURN = "return"

    MOVEMENT_CHOICES = [
        (ADJUSTMENT, "Adjustment"),
        (SALE, "Sale"),
        (RETURN, "Return"),
    ]

    inventory = models.ForeignKey(InventoryRecord, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    quantity = models.IntegerField()
    note = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
