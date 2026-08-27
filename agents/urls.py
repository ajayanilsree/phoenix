from django.urls import path

from . import views

urlpatterns = [
    path("", views.agent_entry, name="agent_entry"),
    path("login/", views.agent_login, name="agent_login"),
    path("dashboard/", views.dashboard, name="agent_dashboard"),
    path("shop/", views.shop, name="agent_shop"),
    path("orders/", views.orders, name="agent_orders"),
    path("customers/", views.customers, name="agent_customers"),
    path("profile/", views.profile, name="agent_profile"),
]
