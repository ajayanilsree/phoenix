from django.urls import path

from .views import PhoenixLoginView, PhoenixLogoutView, post_login_redirect, register

urlpatterns = [
    path("login/", PhoenixLoginView.as_view(), name="login"),
    path("logout/", PhoenixLogoutView.as_view(), name="logout"),
    path("register/", register, name="register"),
    path("redirect/", post_login_redirect, name="post_login_redirect"),
]
