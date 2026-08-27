from django.contrib import admin

from .models import InventoryRecord, StockMovement


@admin.register(InventoryRecord)
class InventoryRecordAdmin(admin.ModelAdmin):
    list_display = ("product", "variant", "current_stock", "low_stock_threshold", "stock_status", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("product__name", "product__sku", "variant__sku")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("inventory", "movement_type", "quantity", "created_by", "created_at")
    list_filter = ("movement_type", "created_at")
