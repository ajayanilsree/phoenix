from django.urls import path

from .views import PhoenixLoginView, PhoenixLogoutView, forgot_password, post_login_redirect, register, resend_otp, reset_password, verify_otp

urlpatterns = [
    path("login/", PhoenixLoginView.as_view(), name="login"),
    path("logout/", PhoenixLogoutView.as_view(), name="logout"),
    path("register/", register, name="register"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("forgot-password/verify/", verify_otp, name="verify_otp"),
    path("forgot-password/resend/", resend_otp, name="resend_otp"),
    path("reset-password/", reset_password, name="reset_password"),
    path("redirect/", post_login_redirect, name="post_login_redirect"),
]
