from django.urls import path

from .views import checkout, order_success, shipping_quote, verify_razorpay_payment

urlpatterns = [
    path("checkout/", checkout, name="checkout"),
    path("checkout/shipping-quote/", shipping_quote, name="shipping_quote"),
    path("checkout/payment/verify/", verify_razorpay_payment, name="verify_razorpay_payment"),
    path("order/<str:order_number>/success/", order_success, name="order_success"),
]
