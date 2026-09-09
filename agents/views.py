from django.contrib.auth import login
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from accounts.decorators import user_role
from accounts.models import AgentWallet
from accounts.forms import AgentLoginForm
from catalog.models import Product
from orders.forms import AddressForm
from orders.models import Address, Order
from orders.rewards import eligible_agent_orders, reconcile_agent_rewards


def paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


@never_cache
def agent_entry(request):
    if request.user.is_authenticated:
        return redirect("agent_dashboard")
    return redirect("agent_login")


@never_cache
def agent_login(request):
    if request.user.is_authenticated:
        return redirect("agent_dashboard")
    form = AgentLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("agent_dashboard")
    return render(request, "dashboard/auth/agent_login.html", {"form": form})


@never_cache
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    reconcile_agent_rewards(request.user)
    orders = Order.objects.filter(Q(agent=request.user) | Q(customer=request.user)).select_related("customer")
    agent_profile = getattr(request.user, "agent_profile", None)
    wallet = AgentWallet.objects.filter(agent=request.user).first()
    query = request.GET.get("q", "").strip()
    lookup_results = Order.objects.none()
    if query:
        lookup_results = orders.filter(Q(order_number__icontains=query) | Q(customer__email__icontains=query))
    orders_using_code = eligible_agent_orders(request.user)
    return render(
        request,
        "agents/dashboard.html",
        {
            "orders": orders[:10],
            "agent_profile": agent_profile,
            "lookup_results": lookup_results,
            "query": query,
            "pending_orders": orders.filter(status__in=["pending", "confirmed", "processing"]).count(),
            "completed_orders": orders.filter(status="delivered").count(),
            "orders_using_code": orders_using_code.count(),
            "total_sales_through_code": orders_using_code.aggregate(total=Sum("grand_total"))["total"] or 0,
            "wallet": wallet,
            "wallet_transactions": wallet.transactions.order_by("-created_at")[:10] if wallet else [],
        },
    )


@never_cache
def shop(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    qs = Product.objects.filter(is_active=True).select_related("category").prefetch_related("images").order_by("name")
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query) | Q(category__name__icontains=query))
    return render(request, "agents/shop.html", {"page_obj": paginate(request, qs, 12), "query": query})


@never_cache
def shop_redirect(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    return redirect("shop")


@never_cache
def orders(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    qs = Order.objects.filter(Q(agent=request.user) | Q(customer=request.user)).select_related("customer")
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(order_number__icontains=query) | Q(customer__email__icontains=query))
    return render(request, "agents/orders.html", {"page_obj": paginate(request, qs, 15), "query": query})


@never_cache
def customers(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    orders = Order.objects.filter(agent=request.user).select_related("customer", "shipping_address")[:30]
    return render(request, "agents/customers.html", {"orders": orders})


@never_cache
def profile(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    return render(request, "agents/profile.html")


@never_cache
def address(request, address_type=None):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    billing_address = Address.objects.filter(user=request.user, address_type=Address.BILLING, is_default=True).order_by("-updated_at", "-id").first()
    delivery_address = Address.objects.filter(user=request.user, address_type=Address.DELIVERY, is_default=True).order_by("-updated_at", "-id").first()
    saved_address = billing_address if address_type == Address.BILLING else delivery_address
    is_editing = address_type in {Address.BILLING, Address.DELIVERY} and (request.method == "POST" or request.GET.get("edit") == "1" or saved_address is None)
    if request.method == "POST" and is_editing:
        form = AddressForm(request.POST, instance=saved_address)
        if form.is_valid():
            agent_address = form.save(commit=False)
            agent_address.user = request.user
            agent_address.address_type = address_type or Address.DELIVERY
            agent_address.is_default = True
            agent_address.save()
            Address.objects.filter(user=request.user, address_type=agent_address.address_type, is_default=True).exclude(pk=agent_address.pk).update(is_default=False)
            messages.success(request, f"Your {agent_address.get_address_type_display().lower()} address has been saved.")
            return redirect("agent_address") if address_type is None else redirect("agent_" + address_type + "_address")
    elif is_editing:
        form = AddressForm(instance=saved_address)
    else:
        form = None
    return render(
        request,
        "agents/address.html",
        {
            "form": form,
            "saved_address": saved_address,
            "billing_address": billing_address,
            "delivery_address": delivery_address,
            "address_type": address_type,
            "is_editing": is_editing,
        },
    )
