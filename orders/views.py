from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import AgentProfile
from cart.models import Cart
from inventory.models import InventoryRecord, StockMovement
from .forms import AgentPromoForm, CheckoutAddressForm
from .models import Address, Order, OrderItem

PROMO_SESSION_KEY = "agent_promo_code"
CHECKOUT_ADDRESS_SESSION_KEY = "checkout_delivery_values"
PENDING_ORDER_SESSION_KEY = "pending_payment_order_id"
ADDRESS_FIELDS = ["full_name", "phone", "line1", "line2", "city", "district", "state", "postal_code", "country"]
MONEY = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def percent_label(value):
    return format(Decimal(value or 0).normalize(), "f")


def get_saved_address(user, address_type=Address.DELIVERY):
    return Address.objects.filter(user=user, address_type=address_type, is_default=True).order_by("-updated_at", "-id").first()


def update_saved_address(user, form, address_type=Address.DELIVERY):
    saved_address = get_saved_address(user, address_type)
    if saved_address is None:
        saved_address = Address(user=user)
    for field in ["full_name", "phone", "line1", "line2", "city", "district", "state", "postal_code", "country"]:
        setattr(saved_address, field, form.cleaned_data[field])
    saved_address.address_type = address_type
    saved_address.is_default = True
    saved_address.save()
    Address.objects.filter(user=user, address_type=address_type, is_default=True).exclude(pk=saved_address.pk).update(is_default=False)
    return saved_address


def checkout_initial(delivery_address, billing_address, saved_values=None):
    source = saved_values or delivery_address or {}
    if isinstance(source, Address):
        initial = {field: getattr(source, field) for field in ADDRESS_FIELDS}
    else:
        initial = {field: source.get(field, "") for field in ADDRESS_FIELDS}
    initial["country"] = initial.get("country") or "India"
    initial["use_saved_delivery"] = saved_values.get("use_saved_delivery", False) if saved_values is not None else bool(delivery_address)
    initial["use_billing_address"] = saved_values.get("use_billing_address", False) if saved_values is not None else False
    initial["save_delivery_address"] = saved_values.get("save_delivery_address", False) if saved_values is not None else False
    return initial


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


def razorpay_client():
    from django.conf import settings

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    try:
        import razorpay
    except ImportError:
        return None
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def stock_error(cart):
    if cart is None:
        return "Your cart is empty."
    for item in cart.items.select_related("product", "variant"):
        inventory = InventoryRecord.objects.filter(variant_id=item.variant_id).first() if item.variant_id else None
        if inventory is None:
            inventory = InventoryRecord.objects.filter(product_id=item.product_id).first()
        available = inventory.current_stock if inventory else 0
        if item.quantity > available:
            return f"Only {max(available, 0)} units of {item.product.name} are currently available."
    return ""


def create_or_update_pending_order(request, cart, form, summary, delivery_address, billing_address):
    pending_id = request.session.get(PENDING_ORDER_SESSION_KEY)
    with transaction.atomic():
        address = billing_address if form.cleaned_data.get("use_billing_address") else delivery_address
        if not form.cleaned_data.get("use_saved_delivery") and not form.cleaned_data.get("use_billing_address"):
            address = form.save(commit=False)
            address.user = request.user
            address.address_type = Address.DELIVERY
            address.is_default = False
            address.save()
        if form.cleaned_data.get("save_delivery_address") and not form.cleaned_data.get("use_saved_delivery"):
            update_saved_address(request.user, form, Address.DELIVERY)

        order = None
        if pending_id:
            order = Order.objects.filter(
                id=pending_id,
                customer=request.user,
                status=Order.PENDING,
                payment_status="pending",
            ).first()
        if order is None:
            order = Order.objects.create(
                order_number=f"PHX-{uuid4().hex[:8].upper()}",
                customer=request.user,
            )
        else:
            order.items.all().delete()
        order.agent = summary["promo"].user if summary["promo"] else None
        order.agent_code_snapshot = summary["promo_code"]
        order.agent_discount_percentage = summary["discount_percentage"]
        order.agent_discount_amount = summary["discount_amount"]
        order.subtotal_before_agent_discount = summary["subtotal"]
        order.discount_total = summary["discount_amount"]
        order.delivery_charge = summary["delivery_charge"]
        order.tax_total = summary["tax_total"]
        order.shipping_address = address
        order.billing_address = billing_address
        order.payment_method = "razorpay"
        order.payment_status = "pending"
        order.status = Order.PENDING
        order.save()
        for item in cart.items.select_related("product", "variant"):
            OrderItem.objects.create(
                order=order,
                product=item.product,
                variant=item.variant,
                product_name=item.product.name,
                sku=item.variant.sku if item.variant else item.product.sku,
                selected_variant=item.variant.name if item.variant else "",
                unit_type=item.product.unit_type,
                unit_price=item.unit_price,
                quantity=item.quantity,
                line_total=item.line_total,
            )
        order.recalculate_totals()
        order.save(update_fields=["subtotal", "grand_total", "updated_at"])
    request.session[PENDING_ORDER_SESSION_KEY] = order.id
    return order


def amount_in_paise(amount):
    return int((money(amount) * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


@login_required
def checkout(request):
    cart = Cart.objects.filter(user=request.user).prefetch_related("items__product", "items__variant").first()
    if not cart or not cart.items.exists():
        request.session.pop(PROMO_SESSION_KEY, None)
        messages.info(request, "Your cart is empty.")
        return redirect("cart_detail")

    billing_address = get_saved_address(request.user, Address.BILLING)
    delivery_address = get_saved_address(request.user, Address.DELIVERY)
    promo_form = AgentPromoForm()
    summary = checkout_summary(cart, request.session.get(PROMO_SESSION_KEY))
    if summary["promo_error"]:
        request.session.pop(PROMO_SESSION_KEY, None)
        summary = checkout_summary(cart)

    if request.method == "POST":
        action = request.POST.get("action", "place_order")
        if action == "apply_promo":
            request.session[CHECKOUT_ADDRESS_SESSION_KEY] = {field: request.POST.get(field, "") for field in ADDRESS_FIELDS}
            request.session[CHECKOUT_ADDRESS_SESSION_KEY].update({
                "use_saved_delivery": request.POST.get("use_saved_delivery") == "on",
                "use_billing_address": request.POST.get("use_billing_address") == "on",
                "save_delivery_address": request.POST.get("save_delivery_address") == "on",
            })
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
            request.session[CHECKOUT_ADDRESS_SESSION_KEY] = {field: request.POST.get(field, "") for field in ADDRESS_FIELDS}
            request.session[CHECKOUT_ADDRESS_SESSION_KEY].update({
                "use_saved_delivery": request.POST.get("use_saved_delivery") == "on",
                "use_billing_address": request.POST.get("use_billing_address") == "on",
                "save_delivery_address": request.POST.get("save_delivery_address") == "on",
            })
            request.session.pop(PROMO_SESSION_KEY, None)
            messages.info(request, "Promo code removed.")
            return redirect("checkout")

        form = CheckoutAddressForm(request.POST)
        form.fields["use_saved_delivery"].disabled = not bool(delivery_address)
        form.fields["use_saved_delivery"].initial = bool(delivery_address)
        if form.is_valid():
            summary = checkout_summary(cart, request.session.get(PROMO_SESSION_KEY))
            if summary["promo_error"]:
                request.session.pop(PROMO_SESSION_KEY, None)
                messages.error(request, summary["promo_error"])
                return redirect("checkout")
            if not razorpay_client():
                messages.error(request, "Online payment is not configured yet. Please try again later.")
                return redirect("checkout")
            error = stock_error(cart)
            if error:
                messages.error(request, error)
                return redirect("checkout")
            order = create_or_update_pending_order(request, cart, form, summary, delivery_address, billing_address)
            try:
                client = razorpay_client()
                receipt = order.order_number
                razorpay_order = client.order.create({
                    "amount": amount_in_paise(order.grand_total),
                    "currency": "INR",
                    "receipt": receipt,
                })
            except Exception:
                order.payment_status = "failed"
                order.save(update_fields=["payment_status", "updated_at"])
                messages.error(request, "We could not start the payment. Please try again.")
                return redirect("checkout")
            order.razorpay_order_id = razorpay_order["id"]
            order.payment_status = "pending"
            order.save(update_fields=["razorpay_order_id", "payment_status", "updated_at"])
            return render(
                request,
                "orders/checkout.html",
                {"form": form, "promo_form": promo_form, "cart": cart, "billing_address": billing_address, "delivery_address": delivery_address, "summary": summary, "razorpay_options": {"key": settings.RAZORPAY_KEY_ID, "amount": amount_in_paise(order.grand_total), "currency": "INR", "name": "Phoenix Interior Hub", "description": f"Order {order.order_number}", "order_id": order.razorpay_order_id, "callback_url": reverse("verify_razorpay_payment"), "prefill": {"name": request.user.get_full_name(), "email": request.user.email, "contact": form.cleaned_data.get("phone", "")}, "theme": {"color": "#0B3158"}}},
            )
    else:
        initial = {}
        initial = checkout_initial(delivery_address, billing_address, request.session.pop(CHECKOUT_ADDRESS_SESSION_KEY, None))
        form = CheckoutAddressForm(initial=initial)
        form.fields["use_saved_delivery"].disabled = not bool(delivery_address)
    return render(
        request,
        "orders/checkout.html",
        {"form": form, "promo_form": promo_form, "cart": cart, "billing_address": billing_address, "delivery_address": delivery_address, "summary": summary},
    )


@login_required
@require_POST
def verify_razorpay_payment(request):
    order_id = request.session.get(PENDING_ORDER_SESSION_KEY)
    order = Order.objects.filter(id=order_id, customer=request.user).first()
    if order is None:
        return JsonResponse({"success": False, "message": "Payment session expired. Please return to checkout."}, status=400)
    payment_id = request.POST.get("razorpay_payment_id", "").strip()
    returned_order_id = request.POST.get("razorpay_order_id", "").strip()
    signature = request.POST.get("razorpay_signature", "").strip()
    if not payment_id or returned_order_id != order.razorpay_order_id or not signature:
        order.payment_status = "failed"
        order.save(update_fields=["payment_status", "updated_at"])
        return JsonResponse({"success": False, "message": "Payment verification failed."}, status=400)
    client = razorpay_client()
    try:
        client.utility.verify_payment_signature({"razorpay_order_id": returned_order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature})
    except Exception:
        order.payment_status = "failed"
        order.save(update_fields=["payment_status", "updated_at"])
        return JsonResponse({"success": False, "message": "Payment verification failed."}, status=400)

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk, customer=request.user)
        if order.payment_status == "paid":
            return JsonResponse({"success": True, "redirect_url": reverse("order_success", args=[order.order_number])})
        error = stock_error(Cart.objects.filter(user=request.user).prefetch_related("items__product", "items__variant").first())
        if error:
            order.payment_status = "failed"
            order.save(update_fields=["payment_status", "updated_at"])
            return JsonResponse({"success": False, "message": error}, status=409)
        for item in order.items.select_related("product", "variant"):
            inventory = InventoryRecord.objects.select_for_update().filter(variant_id=item.variant_id).first() if item.variant_id else None
            if inventory is None:
                inventory = InventoryRecord.objects.select_for_update().filter(product_id=item.product_id).first()
            if inventory is None or inventory.current_stock < item.quantity:
                order.payment_status = "failed"
                order.save(update_fields=["payment_status", "updated_at"])
                return JsonResponse({"success": False, "message": f"Only {max(inventory.current_stock, 0) if inventory else 0} units of {item.product_name} are currently available."}, status=409)
            inventory.current_stock -= item.quantity
            inventory.save(update_fields=["current_stock", "updated_at"])
            StockMovement.objects.create(inventory=inventory, movement_type=StockMovement.SALE, quantity=-item.quantity, note=f"Paid order {order.order_number}")
        order.payment_status = "paid"
        order.status = Order.CONFIRMED
        order.razorpay_payment_id = payment_id
        order.razorpay_signature = signature
        order.save(update_fields=["payment_status", "status", "razorpay_payment_id", "razorpay_signature", "updated_at"])
        Cart.objects.filter(user=request.user).first().items.all().delete()
    request.session.pop(PENDING_ORDER_SESSION_KEY, None)
    request.session.pop(PROMO_SESSION_KEY, None)
    request.session.pop(CHECKOUT_ADDRESS_SESSION_KEY, None)
    return JsonResponse({"success": True, "redirect_url": reverse("order_success", args=[order.order_number])})


@login_required
def order_success(request, order_number):
    order = Order.objects.filter(order_number=order_number, customer=request.user).first()
    if order is None:
        return redirect("customer_orders")
    return render(request, "orders/order_success.html", {"order": order})
