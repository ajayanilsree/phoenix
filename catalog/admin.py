from django.contrib import admin

from .models import Category, Product, ProductAttribute, ProductImage, ProductVariant


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 4


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active", "sort_order")
    list_filter = ("is_active", "parent")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "compare_at_price", "price", "unit_type", "is_featured", "is_trending", "is_active")
    list_filter = ("category", "unit_type", "is_featured", "is_trending", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "sku", "short_description")
    inlines = [ProductVariantInline, ProductAttributeInline, ProductImageInline]


admin.site.register(ProductImage)
admin.site.register(ProductVariant)
admin.site.register(ProductAttribute)
