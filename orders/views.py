from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from accounts.models import AgentProfile
from cart.models import Cart
from .forms import AgentPromoForm, CheckoutAddressForm
from .models import Address, Order, OrderItem

PROMO_SESSION_KEY = "agent_promo_code"
MONEY = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def percent_label(value):
    return format(Decimal(value or 0).normalize(), "f")


def get_saved_address(user):
    return Address.objects.filter(user=user, is_default=True).order_by("-updated_at", "-id").first()


def update_saved_address(user, form):
    saved_address = get_saved_address(user)
    if saved_address is None:
        saved_address = Address(user=user)
    for field in ["full_name", "phone", "line1", "line2", "city", "district", "state", "postal_code", "country"]:
        setattr(saved_address, field, form.cleaned_data[field])
    saved_address.is_default = True
    saved_address.save()
    Address.objects.filter(user=user, is_default=True).exclude(pk=saved_address.pk).update(is_default=False)
    return saved_address


def resolve_agent_promo(code):
    normalized = (code or "").strip().upper()
    if not normalized:
        return None, "Invalid promo code."
    promo = AgentProfile.objects.select_related("user").filter(agent_code__iexact=normalized).order_by("id").first()
    if promo is None:
        return None, "Invalid promo code."
    if not promo.user.is_active:
        return None, "This promo code is currently unavailable."
    if promo.discount_percentage <= 0:
        return None, "This promo code currently has no discount."
    return promo, ""


def checkout_summary(cart, promo_code=None):
    subtotal = money(cart.subtotal)
    promo, error = resolve_agent_promo(promo_code) if promo_code else (None, "")
    percentage = promo.discount_percentage if promo else Decimal("0.00")
    discount_amount = money(subtotal * percentage / Decimal("100")) if promo else Decimal("0.00")
    discounted_subtotal = money(subtotal - discount_amount)
    return {
        "promo": promo,
        "promo_error": error,
        "promo_code": promo.agent_code if promo else "",
        "subtotal": subtotal,
        "discount_percentage": percentage,
        "discount_amount": discount_amount,
        "discounted_subtotal": discounted_subtotal,
        "delivery_charge": Decimal("0.00"),
        "tax_total": Decimal("0.00"),
        "grand_total": discounted_subtotal,
    }


@login_required
def checkout(request):
    cart = Cart.objects.filter(user=request.user).prefetch_related("items__product", "items__variant").first()
    if not cart or not cart.items.exists():
        request.session.pop(PROMO_SESSION_KEY, None)
        messages.info(request, "Your cart is empty.")
        return redirect("cart_detail")

    saved_address = get_saved_address(request.user)
    promo_form = AgentPromoForm()
    summary = checkout_summary(cart, request.session.get(PROMO_SESSION_KEY))
    if summary["promo_error"]:
        request.session.pop(PROMO_SESSION_KEY, None)
        summary = checkout_summary(cart)

    if request.method == "POST":
        action = request.POST.get("action", "place_order")
        if action == "apply_promo":
            promo_form = AgentPromoForm(request.POST)
            if promo_form.is_valid():
                promo, error = resolve_agent_promo(promo_form.cleaned_data["promo_code"])
                if promo:
                    request.session[PROMO_SESSION_KEY] = promo.agent_code
                    messages.success(request, f"Promo code applied — {percent_label(promo.discount_percentage)}% discount")
                else:
                    request.session.pop(PROMO_SESSION_KEY, None)
                    messages.error(request, error)
            return redirect("checkout")
        if action == "remove_promo":
            request.session.pop(PROMO_SESSION_KEY, None)
            messages.info(request, "Promo code removed.")
            return redirect("checkout")

        form = CheckoutAddressForm(request.POST)
        form.fields["save_to_account"].label = (
            "Update my saved address with these details" if saved_address else "Save this address to my account"
        )
        if form.is_valid():
            summary = checkout_summary(cart, request.session.get(PROMO_SESSION_KEY))
            if summary["promo_error"]:
                request.session.pop(PROMO_SESSION_KEY, None)
                messages.error(request, summary["promo_error"])
                return redirect("checkout")
            with transaction.atomic():
                address = form.save(commit=False)
                address.user = request.user
                address.is_default = False
                address.save()
                if form.cleaned_data.get("save_to_account"):
                    update_saved_address(request.user, form)
                order = Order.objects.create(
                    order_number=f"PHX-{uuid4().hex[:8].upper()}",
                    customer=request.user,
                    agent=summary["promo"].user if summary["promo"] else None,
                    agent_code_snapshot=summary["promo_code"],
                    agent_discount_percentage=summary["discount_percentage"],
                    agent_discount_amount=summary["discount_amount"],
                    subtotal_before_agent_discount=summary["subtotal"],
                    discount_total=summary["discount_amount"],
                    delivery_charge=summary["delivery_charge"],
                    tax_total=summary["tax_total"],
                    shipping_address=address,
                    business_notes="Payment, tax, delivery charge and shipping-zone rules require business confirmation.",
                )
                for item in cart.items.select_related("product", "variant"):
                    variant_label = item.variant.name if item.variant else ""
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        variant=item.variant,
                        product_name=item.product.name,
                        sku=item.variant.sku if item.variant else item.product.sku,
                        selected_variant=variant_label,
                        unit_type=item.product.unit_type,
                        unit_price=item.unit_price,
                        quantity=item.quantity,
                        line_total=item.line_total,
                    )
                order.recalculate_totals()
                order.save()
                cart.items.all().delete()
                request.session.pop(PROMO_SESSION_KEY, None)
            messages.success(request, f"Order {order.order_number} placed.")
            return redirect("customer_orders")
    else:
        initial = {}
        if saved_address:
            initial = {
                "full_name": saved_address.full_name,
                "phone": saved_address.phone,
                "line1": saved_address.line1,
                "line2": saved_address.line2,
                "city": saved_address.city,
                "district": saved_address.district,
                "state": saved_address.state,
                "postal_code": saved_address.postal_code,
                "country": saved_address.country,
                "save_to_account": False,
            }
        else:
            initial = {"country": "India", "save_to_account": True}
        form = CheckoutAddressForm(initial=initial)
        form.fields["save_to_account"].label = (
            "Update my saved address with these details" if saved_address else "Save this address to my account"
        )
    return render(
        request,
        "orders/checkout.html",
        {"form": form, "promo_form": promo_form, "cart": cart, "saved_address": saved_address, "summary": summary},
    )
