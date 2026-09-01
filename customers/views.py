from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from orders.forms import CustomerAddressForm
from orders.models import Address
from orders.models import Order


@login_required
@role_required("customer")
def dashboard(request):
    orders = Order.objects.filter(customer=request.user)
    return render(
        request,
        "customers/dashboard.html",
        {
            "recent_orders": orders[:5],
            "pending_orders": orders.filter(status__in=["pending", "confirmed", "processing"]).count(),
            "completed_orders": orders.filter(status="delivered").count(),
        },
    )


@login_required
@role_required("customer")
def orders(request):
    return render(request, "customers/orders.html", {"orders": Order.objects.filter(customer=request.user)})


@login_required
@role_required("customer")
def order_detail(request, order_number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), order_number=order_number, customer=request.user)
    return render(request, "customers/order_detail.html", {"order": order})


@login_required
@role_required("customer")
def profile(request):
    return render(request, "customers/profile.html")


@login_required
@role_required("customer")
def address(request, address_type=None):
    billing_address = Address.objects.filter(user=request.user, address_type=Address.BILLING, is_default=True).order_by("-updated_at", "-id").first()
    delivery_address = Address.objects.filter(user=request.user, address_type=Address.DELIVERY, is_default=True).order_by("-updated_at", "-id").first()
    saved_address = billing_address if address_type == Address.BILLING else delivery_address
    is_editing = address_type in {Address.BILLING, Address.DELIVERY} and (request.method == "POST" or request.GET.get("edit") == "1" or saved_address is None)

    if request.method == "POST":
        form = CustomerAddressForm(request.POST, instance=saved_address)
        if form.is_valid():
            customer_address = form.save(commit=False)
            customer_address.user = request.user
            customer_address.address_type = address_type or Address.DELIVERY
            customer_address.is_default = True
            customer_address.save()
            Address.objects.filter(user=request.user, address_type=customer_address.address_type, is_default=True).exclude(pk=customer_address.pk).update(is_default=False)
            messages.success(request, f"Your {customer_address.get_address_type_display().lower()} address has been saved.")
            return redirect("customer_address") if address_type is None else redirect("customer_" + address_type + "_address")
    else:
        form = CustomerAddressForm(instance=saved_address)

    return render(
        request,
        "customers/address.html",
        {
            "form": form,
            "saved_address": saved_address,
            "billing_address": billing_address,
            "delivery_address": delivery_address,
            "address_type": address_type,
            "is_editing": is_editing,
        },
    )
