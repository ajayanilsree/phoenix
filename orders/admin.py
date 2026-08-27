from django.contrib import admin

from .models import Address, Order, OrderItem, PaymentRecord


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total",)


class PaymentInline(admin.TabularInline):
    model = PaymentRecord
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "agent_code_snapshot", "status", "payment_status", "grand_total", "created_at")
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("order_number", "customer__username", "customer__email", "agent_code_snapshot")
    inlines = [OrderItemInline, PaymentInline]


admin.site.register(Address)
admin.site.register(OrderItem)
admin.site.register(PaymentRecord)
