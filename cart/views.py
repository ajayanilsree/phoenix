from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Product, ProductVariant
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
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get("quantity", 1))
    if quantity <= 0:
        item.delete()
    else:
        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])
    return redirect("cart_detail")


@login_required
def remove_cart_item(request, item_id):
    get_object_or_404(CartItem, id=item_id, cart__user=request.user).delete()
    messages.info(request, "Item removed from cart.")
    return redirect("cart_detail")
