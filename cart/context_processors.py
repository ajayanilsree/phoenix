from .models import Cart


def cart_summary(request):
    count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).prefetch_related("items").first()
        count = cart.total_items if cart else 0
    return {"cart_item_count": count}
