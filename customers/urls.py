from django.urls import path

from .views import address, dashboard, order_detail, orders, profile

urlpatterns = [
    path("", dashboard, name="customer_dashboard"),
    path("orders/", orders, name="customer_orders"),
    path("orders/<str:order_number>/", order_detail, name="customer_order_detail"),
    path("profile/", profile, name="customer_profile"),
    path("address/", address, name="customer_address"),
    path("address/billing/", address, {"address_type": "billing"}, name="customer_billing_address"),
    path("address/delivery/", address, {"address_type": "delivery"}, name="customer_delivery_address"),
]
