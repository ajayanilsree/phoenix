from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from accounts.decorators import user_role
from accounts.forms import AgentLoginForm
from catalog.models import Product
from orders.models import Order


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
    orders = Order.objects.filter(agent=request.user).select_related("customer")
    agent_profile = getattr(request.user, "agent_profile", None)
    query = request.GET.get("q", "").strip()
    lookup_results = Order.objects.none()
    if query:
        lookup_results = orders.filter(Q(order_number__icontains=query) | Q(customer__email__icontains=query))
    orders_using_code = orders.filter(agent_code_snapshot__gt="")
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
def orders(request):
    if not request.user.is_authenticated:
        return redirect("agent_login")
    if user_role(request.user) != "agent":
        raise PermissionDenied
    qs = Order.objects.filter(agent=request.user).select_related("customer")
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
