from django.urls import path

from .views import address, dashboard, order_detail, orders, profile
from orders import invoice_views

urlpatterns = [
    path("", dashboard, name="customer_dashboard"),
    path("orders/", orders, name="customer_orders"),
    path("orders/<str:order_number>/", order_detail, name="customer_order_detail"),
    path("profile/", profile, name="customer_profile"),
    path("address/", address, name="customer_address"),
    path("address/billing/", address, {"address_type": "billing"}, name="customer_billing_address"),
    path("address/delivery/", address, {"address_type": "delivery"}, name="customer_delivery_address"),
    path("invoices/", invoice_views.customer_invoices, name="customer_invoices"),
    path("invoices/<int:invoice_id>/", invoice_views.customer_invoice_detail, name="customer_invoice_detail"),
    path("invoices/<int:invoice_id>/pdf/", invoice_views.customer_invoice_pdf, name="customer_invoice_pdf"),
]
