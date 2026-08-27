from django.urls import path

from . import views

urlpatterns = [
    path("", views.employee_entry, name="employee_entry"),
    path("login/", views.employee_login, name="employee_login"),
    path("dashboard/", views.dashboard, name="employee_dashboard"),
    path("dashboard/", views.dashboard, name="staff_dashboard"),
    path("orders/", views.orders, name="employee_orders"),
    path("orders/<str:order_number>/", views.order_detail, name="employee_order_detail"),
    path("orders/<str:order_number>/status/", views.update_order_status, name="staff_update_order_status"),
    path("products/", views.products, name="employee_products"),
    path("inventory/", views.inventory, name="employee_inventory"),
    path("inventory/<int:record_id>/edit/", views.inventory_edit, name="employee_inventory_edit"),
    path("customers/", views.customers, name="employee_customers"),
    path("profile/", views.profile, name="employee_profile"),
]
