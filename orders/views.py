from decimal import Decimal, ROUND_HALF_UP
import logging
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import user_role
from accounts.models import AgentProfile, AgentWallet, AgentWalletTransaction, UserProfile
from cart.models import Cart
from inventory.models import InventoryRecord, StockMovement
from .forms import AgentPromoForm, CheckoutAddressForm
from .models import Address, Order, OrderItem
from .payment import get_razorpay_client

PROMO_SESSION_KEY = "agent_promo_code"
SUBPROMO_SESSION_KEY = "agent_subpromo_code"
REDEEM_POINTS_SESSION_KEY = "agent_redeem_points"
CHECKOUT_ADDRESS_SESSION_KEY = "checkout_delivery_values"
PENDING_ORDER_SESSION_KEY = "pending_payment_order_id"
ADDRESS_FIELDS = ["full_name", "phone", "line1", "line2", "city", "district", "state", "postal_code", "country"]
MONEY = Decimal("0.01")
logger = logging.getLogger(__name__)


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
    return promo, ""


def checkout_summary(cart, promo_code=None, subpromo_code=None, redeem_points=0, user=None):
    role = user_role(user) if user else UserProfile.CUSTOMER
    is_agent = role == UserProfile.AGENT
    promo = None
    error = ""
    if is_agent:
        agent = getattr(user, "agent_profile", None)
        if subpromo_code:
            if not agent or not agent.subpromo_code or agent.subpromo_code.casefold() != subpromo_code.strip().casefold():
                error = "Invalid Subpromo Code for this Agent account."
        subpromo_code = agent.subpromo_code if agent and subpromo_code and not error else ""
    elif promo_code:
        promo, error = resolve_agent_promo(promo_code)
        promo_code = promo.agent_code if promo else ""
    lines = []
    subtotal = Decimal("0.00")
    discounted_subtotal = Decimal("0.00")
    for item in cart.items.select_related("product", "variant"):
        source = item.variant or item.product
        selling = money(item.unit_price)
        promo_price = getattr(source, "promo_price", None)
        subpromo_price = getattr(source, "subpromo_price", None)
        applied = selling
        pricing_type = "normal"
        if is_agent and subpromo_code and subpromo_price is not None:
            applied = money(subpromo_price)
            pricing_type = "subpromo"
        elif not is_agent and promo and promo_price is not None:
            applied = money(promo_price)
            pricing_type = "promo"
        subtotal += selling * item.quantity
        discounted_subtotal += applied * item.quantity
        lines.append({"item": item, "selling_price": selling, "promo_price": promo_price, "subpromo_price": subpromo_price, "redeem_percentage": getattr(source, "agent_redeem_percentage", 0), "applied_price": applied, "line_total": money(applied * item.quantity), "pricing_type": pricing_type})
    subtotal = money(subtotal)
    discounted_subtotal = money(discounted_subtotal)
    price_discount = money(subtotal - discounted_subtotal)
    wallet = AgentWallet.objects.filter(agent=user).first() if is_agent and user else None
    available_points = wallet.balance if wallet else Decimal("0.00")
    try:
        requested_points = max(Decimal(str(redeem_points or 0)), Decimal("0.00"))
    except Exception:
        requested_points = Decimal("0.00")
    if not is_agent:
        requested_points = Decimal("0.00")
    if requested_points > available_points:
        error = error or f"You have only {available_points.quantize(MONEY)} redeemable points."
        requested_points = Decimal("0.00")
    wallet_discount = min(money(requested_points), discounted_subtotal)
    grand_total = money(discounted_subtotal - wallet_discount)
    return {
        "promo": promo,
        "promo_error": error,
        "promo_code": promo.agent_code if promo else "",
        "subpromo_code": subpromo_code or "",
        "is_agent": is_agent,
        "lines": lines,
        "subtotal": subtotal,
        "discount_percentage": promo.discount_percentage if promo else Decimal("0.00"),
        "discount_amount": price_discount,
        "discounted_subtotal": discounted_subtotal,
        "available_points": available_points,
        "wallet_points_redeemed": requested_points,
        "wallet_discount_amount": wallet_discount,
        "delivery_charge": Decimal("0.00"),
        "tax_total": Decimal("0.00"),
        "grand_total": grand_total,
    }


def stock_error(cart):
    if cart is None:
        return "Your cart is empty."
    for item in cart.items.select_related("product", "variant"):
        if item.variant_id:
            available = item.variant.stock
        else:
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
        order.promo_code_snapshot = summary["promo_code"]
        order.subpromo_code_snapshot = summary["subpromo_code"]
        order.wallet_points_redeemed = summary["wallet_points_redeemed"]
        order.wallet_discount_amount = summary["wallet_discount_amount"]
        order.agent_discount_percentage = summary["discount_percentage"]
        order.agent_discount_amount = summary["discount_amount"]
        order.subtotal_before_agent_discount = summary["subtotal"]
        order.discount_total = summary["wallet_discount_amount"]
        order.delivery_charge = summary["delivery_charge"]
        order.tax_total = summary["tax_total"]
        order.shipping_address = address
        order.billing_address = billing_address
        order.payment_method = "razorpay"
        order.payment_status = "pending"
        order.status = Order.PENDING
        order.save()
        line_map = {line["item"].id: line for line in summary["lines"]}
        reward_total = Decimal("0.00")
        for item in cart.items.select_related("product", "variant"):
            line = line_map[item.id]
            source = item.variant or item.product
            quantity = item.quantity
            if summary["promo"] and line["promo_price"] is not None and line["subpromo_price"] is not None and line["promo_price"] > line["subpromo_price"]:
                reward_total += money(line["promo_price"] - line["subpromo_price"]) * Decimal(str(line["redeem_percentage"] or 0)) / Decimal("100") * quantity
            OrderItem.objects.create(
                order=order,
                product=item.product,
                variant=item.variant,
                product_name=item.product.name,
                sku=item.variant.sku if item.variant else item.product.sku,
                hsn_code=(item.variant.hsn_code or item.product.hsn_code) if item.variant else item.product.hsn_code,
                selected_variant=item.variant.name if item.variant else "",
                variant_sku=item.variant.sku if item.variant else "",
                variant_size=item.variant.size if item.variant else "",
                variant_colour=item.variant.colour if item.variant else "",
                variant_thickness=item.variant.thickness if item.variant else "",
                variant_finish=item.variant.finish if item.variant else "",
                unit_type=(item.variant.unit_type or item.product.unit_type) if item.variant else item.product.unit_type,
                selling_price_snapshot=line["selling_price"],
                promo_price_snapshot=line["promo_price"],
                subpromo_price_snapshot=line["subpromo_price"],
                agent_redeem_percentage_snapshot=line["redeem_percentage"] or 0,
                applied_price_snapshot=line["applied_price"],
                pricing_type=line["pricing_type"],
                unit_price=line["applied_price"],
                quantity=item.quantity,
                line_total=line["line_total"],
            )
        order.agent_reward_points = money(reward_total)
        order.recalculate_totals()
        order.save(update_fields=["subtotal", "grand_total", "updated_at"])
    request.session[PENDING_ORDER_SESSION_KEY] = order.id
    return order


def amount_in_paise(amount):
    return int((money(amount) * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def finalize_wallet_transactions(order):
    if order.agent_id and order.agent_reward_points > 0:
        wallet, _ = AgentWallet.objects.select_for_update().get_or_create(agent_id=order.agent_id)
        reference = f"order:{order.id}:earn"
        if not AgentWalletTransaction.objects.filter(reference=reference).exists():
            points = money(order.agent_reward_points)
            AgentWalletTransaction.objects.create(wallet=wallet, transaction_type=AgentWalletTransaction.EARN, points=points, order=order, reference=reference, description=f"Reward for order {order.order_number}")
            wallet.balance = money(wallet.balance + points)
            wallet.save(update_fields=["balance", "updated_at"])
    if order.wallet_points_redeemed > 0 and user_role(order.customer) == UserProfile.AGENT:
        wallet = AgentWallet.objects.select_for_update().get_or_create(agent_id=order.customer_id)[0]
        reference = f"order:{order.id}:redeem"
        if not AgentWalletTransaction.objects.filter(reference=reference).exists():
            points = money(order.wallet_points_redeemed)
            if wallet.balance < points:
                raise ValueError("Insufficient wallet points.")
            AgentWalletTransaction.objects.create(wallet=wallet, transaction_type=AgentWalletTransaction.REDEEM, points=-points, order=order, reference=reference, description=f"Redeemed on order {order.order_number}")
            wallet.balance = money(wallet.balance - points)
            wallet.save(update_fields=["balance", "updated_at"])


@login_required
def checkout(request):
    cart = Cart.objects.filter(user=request.user).prefetch_related("items__product", "items__variant").first()
    if not cart or not cart.items.exists():
        request.session.pop(PROMO_SESSION_KEY, None)
        request.session.pop(SUBPROMO_SESSION_KEY, None)
        request.session.pop(REDEEM_POINTS_SESSION_KEY, None)
        messages.info(request, "Your cart is empty.")
        return redirect("cart_detail")

    billing_address = get_saved_address(request.user, Address.BILLING)
    delivery_address = get_saved_address(request.user, Address.DELIVERY)
    promo_form = AgentPromoForm()
    is_agent = user_role(request.user) == UserProfile.AGENT
    summary = checkout_summary(cart, request.session.get(PROMO_SESSION_KEY), request.session.get(SUBPROMO_SESSION_KEY), request.session.get(REDEEM_POINTS_SESSION_KEY), request.user)
    if summary["promo_error"]:
        request.session.pop(PROMO_SESSION_KEY, None)
        request.session.pop(SUBPROMO_SESSION_KEY, None)
        request.session.pop(REDEEM_POINTS_SESSION_KEY, None)
        summary = checkout_summary(cart, user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "place_order")
        if action in {"apply_promo", "apply_subpromo"}:
            request.session[CHECKOUT_ADDRESS_SESSION_KEY] = {field: request.POST.get(field, "") for field in ADDRESS_FIELDS}
            request.session[CHECKOUT_ADDRESS_SESSION_KEY].update({
                "use_saved_delivery": request.POST.get("use_saved_delivery") == "on",
                "use_billing_address": request.POST.get("use_billing_address") == "on",
                "save_delivery_address": request.POST.get("save_delivery_address") == "on",
            })
            code = request.POST.get("promo_code" if not is_agent else "subpromo_code", "").strip().upper()
            if not code:
                request.session.pop(SUBPROMO_SESSION_KEY if is_agent else PROMO_SESSION_KEY, None)
                if is_agent:
                    request.session.pop(REDEEM_POINTS_SESSION_KEY, None)
                else:
                    request.session.pop(PROMO_SESSION_KEY, None)
                messages.info(request, "Enter a promo code to apply.")
                return redirect("checkout")
            if is_agent:
                agent = getattr(request.user, "agent_profile", None)
                if agent and agent.subpromo_code and agent.subpromo_code.casefold() == code.casefold():
                    request.session[SUBPROMO_SESSION_KEY] = agent.subpromo_code
                    messages.success(request, "Sub promo code applied.")
                else:
                    request.session.pop(SUBPROMO_SESSION_KEY, None)
                    messages.error(request, "Invalid Subpromo Code for this Agent account.")
            else:
                promo, error = resolve_agent_promo(code)
                if promo:
                    request.session[PROMO_SESSION_KEY] = promo.agent_code
                    messages.success(request, "Promo code applied.")
                else:
                    request.session.pop(PROMO_SESSION_KEY, None)
                    messages.error(request, error)
            return redirect("checkout")
        if action == "apply_points":
            if is_agent:
                request.session[REDEEM_POINTS_SESSION_KEY] = request.POST.get("redeem_points", "0")
            return redirect("checkout")
        if action == "remove_promo":
            request.session[CHECKOUT_ADDRESS_SESSION_KEY] = {field: request.POST.get(field, "") for field in ADDRESS_FIELDS}
            request.session[CHECKOUT_ADDRESS_SESSION_KEY].update({
                "use_saved_delivery": request.POST.get("use_saved_delivery") == "on",
                "use_billing_address": request.POST.get("use_billing_address") == "on",
                "save_delivery_address": request.POST.get("save_delivery_address") == "on",
            })
            request.session.pop(SUBPROMO_SESSION_KEY if is_agent else PROMO_SESSION_KEY, None)
            messages.info(request, "Promo code removed.")
            return redirect("checkout")
        if action == "remove_points":
            request.session.pop(REDEEM_POINTS_SESSION_KEY, None)
            return redirect("checkout")

        form = CheckoutAddressForm(request.POST)
        form.fields["use_saved_delivery"].disabled = not bool(delivery_address)
        form.fields["use_saved_delivery"].initial = bool(delivery_address)
        if form.is_valid():
            summary = checkout_summary(cart, request.session.get(PROMO_SESSION_KEY), request.session.get(SUBPROMO_SESSION_KEY), request.session.get(REDEEM_POINTS_SESSION_KEY), request.user)
            if summary["promo_error"]:
                request.session.pop(PROMO_SESSION_KEY, None)
                request.session.pop(SUBPROMO_SESSION_KEY, None)
                request.session.pop(REDEEM_POINTS_SESSION_KEY, None)
                messages.error(request, summary["promo_error"])
                return redirect("checkout")
            try:
                client = get_razorpay_client()
            except ImproperlyConfigured as exc:
                logger.error("Razorpay is unavailable: %s", exc)
                messages.error(request, "Online payment is not configured yet. Please try again later.")
                return redirect("checkout")
            error = stock_error(cart)
            if error:
                messages.error(request, error)
                return redirect("checkout")
            order = create_or_update_pending_order(request, cart, form, summary, delivery_address, billing_address)
            try:
                receipt = order.order_number
                razorpay_order = client.order.create({
                    "amount": amount_in_paise(order.grand_total),
                    "currency": "INR",
                    "receipt": receipt,
                })
            except Exception as exc:
                logger.exception("Razorpay order creation failed for %s: %s", order.order_number, exc)
                order.payment_status = "failed"
                order.save(update_fields=["payment_status", "updated_at"])
                if "authentication failed" in str(exc).lower():
                    messages.error(request, "Razorpay rejected the configured payment keys. Please update the Razorpay credentials and try again.")
                else:
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
    try:
        client = get_razorpay_client()
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
            if item.variant_id:
                if item.variant.stock < item.quantity:
                    order.payment_status = "failed"
                    order.save(update_fields=["payment_status", "updated_at"])
                    return JsonResponse({"success": False, "message": f"Only {max(item.variant.stock, 0)} units of {item.product_name} are currently available."}, status=409)
                item.variant.stock -= item.quantity
                item.variant.save(update_fields=["stock", "updated_at"])
                continue
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
        finalize_wallet_transactions(order)
        Cart.objects.filter(user=request.user).first().items.all().delete()
    request.session.pop(PENDING_ORDER_SESSION_KEY, None)
    request.session.pop(PROMO_SESSION_KEY, None)
    request.session.pop(SUBPROMO_SESSION_KEY, None)
    request.session.pop(REDEEM_POINTS_SESSION_KEY, None)
    request.session.pop(CHECKOUT_ADDRESS_SESSION_KEY, None)
    return JsonResponse({"success": True, "redirect_url": reverse("order_success", args=[order.order_number])})


@login_required
def order_success(request, order_number):
    order = Order.objects.filter(order_number=order_number, customer=request.user).first()
    if order is None:
        return redirect("customer_orders")
    return render(request, "orders/order_success.html", {"order": order})
