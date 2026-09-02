from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.decorators import user_role
from accounts.forms import EmployeeLoginForm
from catalog.models import Category, Product, ProductVariant
from dashboard.forms import InventoryUpdateForm, OrderStatusForm, ProductVariantInventoryUpdateForm
from inventory.models import InventoryRecord, StockMovement
from orders.models import Order
from dashboard.views import product_form as shared_product_form
from dashboard.views import product_image_delete as shared_product_image_delete
from dashboard.views import product_toggle as shared_product_toggle


def paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


@never_cache
def employee_entry(request):
    if request.user.is_authenticated:
        return redirect("employee_dashboard")
    return redirect("employee_login")


@never_cache
def employee_login(request):
    if request.user.is_authenticated:
        return redirect("employee_dashboard")
    form = EmployeeLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("employee_dashboard")
    return render(request, "dashboard/auth/employee_login.html", {"form": form})


@never_cache
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    orders = Order.objects.select_related("customer")
    low_stock = InventoryRecord.objects.select_related("product").filter(current_stock__lte=5)
    today = timezone.localdate()
    return render(
        request,
        "staff_portal/dashboard.html",
        {
            "orders": orders[:10],
            "pending_orders": orders.filter(status__in=["pending", "confirmed"]).count(),
            "processing_orders": orders.filter(status="processing").count(),
            "orders_today": orders.filter(created_at__date=today).count(),
            "low_stock_count": low_stock.count(),
            "product_count": Product.objects.filter(is_active=True).count(),
            "low_stock": low_stock[:10],
        },
    )


@never_cache
def update_order_status(request, order_number):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    order = get_object_or_404(Order, order_number=order_number)
    if request.method == "POST":
        order.status = request.POST.get("status", order.status)
        order.save(update_fields=["status", "updated_at"])
        messages.success(request, "Order status updated.")
    return redirect(request.POST.get("next") or "employee_orders")


@never_cache
def orders(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    qs = Order.objects.select_related("customer")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        qs = qs.filter(Q(order_number__icontains=query) | Q(customer__email__icontains=query) | Q(customer__username__icontains=query))
    if status:
        qs = qs.filter(status=status)
    return render(request, "staff_portal/orders.html", {"page_obj": paginate(request, qs, 15), "query": query, "status": status, "status_choices": Order.STATUS_CHOICES})


@never_cache
def order_detail(request, order_number):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    order = get_object_or_404(Order.objects.select_related("customer", "shipping_address").prefetch_related("items"), order_number=order_number)
    form = OrderStatusForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Order status updated.")
        return redirect("employee_order_detail", order_number=order.order_number)
    return render(request, "staff_portal/order_detail.html", {"order": order, "form": form})


@never_cache
def products(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    qs = Product.objects.select_related("category").prefetch_related("images", "variants").order_by("name")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    active = request.GET.get("active", "").strip()
    featured = request.GET.get("featured", "").strip()
    trending = request.GET.get("trending", "").strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if category:
        qs = qs.filter(category__slug=category)
    if active in {"1", "0"}:
        qs = qs.filter(is_active=active == "1")
    if featured in {"1", "0"}:
        qs = qs.filter(is_featured=featured == "1")
    if trending in {"1", "0"}:
        qs = qs.filter(is_trending=trending == "1")
    return render(request, "staff_portal/products.html", {
        "page_obj": paginate(request, qs, 15),
        "categories": Category.objects.filter(is_active=True, parent__isnull=True),
        "query": query,
        "selected_category": category,
        "active": active,
        "featured": featured,
        "trending": trending,
    })


@never_cache
def product_form(request, product_id=None):
    return shared_product_form(request, product_id=product_id, staff_portal=True)


@never_cache
def product_image_delete(request, product_id, image_id):
    return shared_product_image_delete(request, product_id, image_id, staff_portal=True)


@never_cache
def product_toggle(request, product_id):
    return shared_product_toggle(request, product_id, staff_portal=True)


@never_cache
def inventory(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    qs = InventoryRecord.objects.select_related("product", "variant").order_by("product__name")
    variants = ProductVariant.objects.select_related("product").filter(is_active=True).order_by("product__name", "name")
    query = request.GET.get("q", "").strip()
    if query:
        query_filter = Q(product__name__icontains=query) | Q(product__sku__icontains=query) | Q(variant__sku__icontains=query)
        qs = qs.filter(query_filter)
        variants = variants.filter(Q(product__name__icontains=query) | Q(product__sku__icontains=query) | Q(sku__icontains=query))
    status = request.GET.get("status", "").strip()
    if status == "low":
        qs = qs.filter(current_stock__gt=0, current_stock__lte=F("low_stock_threshold"))
        variants = variants.filter(stock__gt=0, stock__lte=F("low_stock_threshold"))
    elif status == "out":
        qs = qs.filter(current_stock__lte=0)
        variants = variants.filter(stock__lte=0)
    return render(request, "staff_portal/inventory.html", {"page_obj": paginate(request, qs, 15), "variant_page_obj": paginate(request, variants, 15), "query": query, "status": status})


@never_cache
def inventory_edit(request, record_id):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    if not getattr(getattr(request.user, "staff_profile", None), "can_update_stock", False):
        raise PermissionDenied
    record = get_object_or_404(InventoryRecord, pk=record_id)
    old_stock = record.current_stock
    form = InventoryUpdateForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        delta = record.current_stock - old_stock
        if delta:
            StockMovement.objects.create(inventory=record, movement_type=StockMovement.ADJUSTMENT, quantity=delta, created_by=request.user, note=form.cleaned_data.get("note", ""))
        messages.success(request, "Inventory updated.")
        return redirect("employee_inventory")
    return render(request, "staff_portal/inventory_form.html", {"form": form, "record": record})


@never_cache
def variant_inventory_edit(request, variant_id):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    if not getattr(getattr(request.user, "staff_profile", None), "can_update_stock", False):
        raise PermissionDenied
    variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=variant_id, is_active=True)
    old_stock = variant.stock
    form = ProductVariantInventoryUpdateForm(request.POST or None, instance=variant)
    if request.method == "POST" and form.is_valid():
        variant = form.save()
        delta = variant.stock - old_stock
        if delta and hasattr(variant, "inventory"):
            StockMovement.objects.create(inventory=variant.inventory, movement_type=StockMovement.ADJUSTMENT, quantity=delta, created_by=request.user, note=form.cleaned_data.get("note", ""))
        messages.success(request, "Variant inventory updated.")
        return redirect("employee_inventory")
    return render(request, "staff_portal/variant_inventory_form.html", {"form": form, "variant": variant})


@never_cache
def customers(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    orders = Order.objects.select_related("customer", "shipping_address")[:30]
    return render(request, "staff_portal/customers.html", {"orders": orders})


@never_cache
def profile(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != "staff":
        raise PermissionDenied
    return render(request, "staff_portal/profile.html")
