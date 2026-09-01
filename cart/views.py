from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Product, ProductVariant
from inventory.models import InventoryRecord
from .models import Cart, CartItem


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def cart_detail(request):
    cart = get_cart(request.user)
    cart_items = cart.items.select_related("product", "variant").prefetch_related("product__images")
    return render(request, "cart/cart_detail.html", {"cart": cart, "cart_items": cart_items})


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    variant_id = request.POST.get("variant")
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, id=variant_id, product=product, is_active=True)
    quantity = max(int(request.POST.get("quantity", 1)), 1)
    cart = get_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, variant=variant, defaults={"quantity": quantity})
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])
    messages.success(request, "Product added to cart.")
    return redirect(request.POST.get("next") or "cart_detail")


@login_required
@require_POST
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related("cart", "product", "variant"), id=item_id, cart__user=request.user)
    raw_quantity = request.POST.get("quantity", "")
    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "message": "Enter a whole-number quantity."}, status=400)
    if quantity < 1:
        return JsonResponse({"success": False, "message": "Quantity must be at least 1."}, status=400)

    inventory = InventoryRecord.objects.filter(variant_id=item.variant_id).first() if item.variant_id else None
    if inventory is None:
        inventory = InventoryRecord.objects.filter(product_id=item.product_id).first()
    if inventory is not None and quantity > inventory.current_stock:
        return JsonResponse({"success": False, "message": f"Only {max(inventory.current_stock, 0)} units are available.", "quantity": item.quantity}, status=400)

    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    cart = item.cart
    subtotal = cart.subtotal or Decimal("0.00")
    return JsonResponse({"success": True, "quantity": item.quantity, "item_subtotal": f"{item.line_total:.2f}", "cart_subtotal": f"{subtotal:.2f}", "cart_count": cart.total_items})


@login_required
def remove_cart_item(request, item_id):
    get_object_or_404(CartItem, id=item_id, cart__user=request.user).delete()
    messages.info(request, "Item removed from cart.")
    return redirect("cart_detail")
