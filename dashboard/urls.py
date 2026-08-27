from django.urls import path

from . import views

urlpatterns = [
    path("", views.admin_entry, name="phoenix_admin_entry"),
    path("login/", views.admin_login, name="phoenix_admin_login"),
    path("dashboard/", views.dashboard, name="admin_dashboard"),
    path("orders/", views.orders, name="admin_orders"),
    path("orders/<str:order_number>/", views.order_detail, name="admin_order_detail"),
    path("products/", views.products, name="admin_products"),
    path("products/add/", views.product_form, name="admin_product_add"),
    path("products/<int:product_id>/edit/", views.product_form, name="admin_product_edit"),
    path("products/<int:product_id>/toggle/", views.product_toggle, name="admin_product_toggle"),
    path("categories/", views.categories, name="admin_categories"),
    path("categories/add/", views.category_form, name="admin_category_add"),
    path("categories/<int:category_id>/edit/", views.category_form, name="admin_category_edit"),
    path("inventory/", views.inventory, name="admin_inventory"),
    path("inventory/<int:record_id>/edit/", views.inventory_edit, name="admin_inventory_edit"),
    path("featured-products/", views.featured_products, name="admin_featured_products"),
    path("trending-materials/", views.trending_materials, name="admin_trending_materials"),
    path("customers/", views.customers, name="admin_customers"),
    path("customers/<int:customer_id>/", views.customer_detail, name="admin_customer_detail"),
    path("employees/", views.employees, name="admin_employees"),
    path("employees/add/", views.employee_form, name="admin_employee_add"),
    path("employees/<int:user_id>/edit/", views.employee_form, name="admin_employee_edit"),
    path("agents/", views.agents, name="admin_agents"),
    path("agents/add/", views.agent_form, name="admin_agent_add"),
    path("agents/<int:user_id>/edit/", views.agent_form, name="admin_agent_edit"),
    path("analytics/", views.analytics, name="admin_analytics"),
    path("settings/", views.settings, name="admin_settings"),
]
