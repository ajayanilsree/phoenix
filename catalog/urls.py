from django.urls import path

from .views import category_detail, product_detail, shop

urlpatterns = [
    path("shop/", shop, name="shop"),
    path("shop/<slug:main_slug>/", shop, name="shop_catalogue_main"),
    path("shop/<slug:main_slug>/<slug:sub_slug>/", shop, name="shop_catalogue_sub"),
    path("category/<slug:slug>/", category_detail, name="category_detail"),
    path("product/<slug:slug>/", product_detail, name="product_detail"),
]
