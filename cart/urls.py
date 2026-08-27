from django.urls import path

from .views import add_to_cart, cart_detail, remove_cart_item, update_cart_item

urlpatterns = [
    path("cart/", cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", add_to_cart, name="add_to_cart"),
    path("cart/item/<int:item_id>/update/", update_cart_item, name="update_cart_item"),
    path("cart/item/<int:item_id>/remove/", remove_cart_item, name="remove_cart_item"),
]
