from django.urls import path

from . import views
from orders import invoice_views

urlpatterns = [
    path("", views.agent_entry, name="agent_entry"),
    path("login/", views.agent_login, name="agent_login"),
    path("dashboard/", views.dashboard, name="agent_dashboard"),
    path("shop/", views.shop_redirect, name="agent_shop"),
    path("orders/", views.orders, name="agent_orders"),
    path("invoices/", invoice_views.agent_invoices, name="agent_invoices"),
    path("invoices/<int:invoice_id>/", invoice_views.agent_invoice_detail, name="agent_invoice_detail"),
    path("invoices/<int:invoice_id>/pdf/", invoice_views.agent_invoice_pdf, name="agent_invoice_pdf"),
    path("customers/", views.customers, name="agent_customers"),
    path("profile/", views.profile, name="agent_profile"),
    path("address/", views.address, name="agent_address"),
    path("address/billing/", views.address, {"address_type": "billing"}, name="agent_billing_address"),
    path("address/delivery/", views.address, {"address_type": "delivery"}, name="agent_delivery_address"),
]
