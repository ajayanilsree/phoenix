import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from accounts.models import AgentProfile, StaffProfile, UserProfile
from accounts.decorators import user_role
from accounts.forms import AdminLoginForm
from catalog.models import Category, Product, ProductImage, ProductReview
from inventory.models import InventoryRecord, StockMovement
from orders.models import Order, OrderItem
from .forms import (
    AgentManageForm,
    CategoryNameForm,
    EmployeeManageForm,
    InventoryUpdateForm,
    OrderStatusForm,
    ProductManageForm,
    ProductVariantFormSet,
)


def require_admin(request):
    if not request.user.is_authenticated:
        return redirect("phoenix_admin_login")
    if user_role(request.user) != "admin":
        raise PermissionDenied
    return None


def require_staff(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")
    if user_role(request.user) != UserProfile.STAFF:
        raise PermissionDenied
    return None


def paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


@never_cache
def admin_entry(request):
    if request.user.is_authenticated:
        if user_role(request.user) != "admin":
            logout(request)
            messages.info(request, "Please log in with a Phoenix Interior Hub Admin account.")
            return redirect("phoenix_admin_login")
        return redirect("admin_dashboard")
    return redirect("phoenix_admin_login")


@never_cache
def admin_login(request):
    if request.user.is_authenticated:
        if user_role(request.user) != "admin":
            logout(request)
            messages.info(request, "Please log in with a Phoenix Interior Hub Admin account.")
            return redirect("phoenix_admin_login")
        return redirect("admin_dashboard")
    form = AdminLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("admin_dashboard")
    return render(request, "dashboard/auth/admin_login.html", {"form": form})


@never_cache
def dashboard(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    orders = Order.objects.select_related("customer")
    low_stock = InventoryRecord.objects.select_related("product").filter(current_stock__lte=5)
    completed_statuses = ["confirmed", "processing", "packed", "shipped", "delivered"]
    total_revenue = (
        orders.filter(payment_status="paid", status__in=completed_statuses).aggregate(total=Sum("grand_total"))["total"]
        or 0
    )
    return render(
        request,
        "dashboard/admin_dashboard.html",
        {
            "total_revenue": total_revenue,
            "total_orders": orders.count(),
            "pending_orders": orders.filter(status__in=["pending", "confirmed", "processing"]).count(),
            "completed_orders": orders.filter(status="delivered").count(),
            "customer_count": User.objects.filter(profile__role="customer").count(),
            "employee_count": User.objects.filter(profile__role="staff", is_active=True).count(),
            "agent_count": User.objects.filter(profile__role="agent", is_active=True).count(),
            "product_count": Product.objects.count(),
            "active_product_count": Product.objects.filter(is_active=True).count(),
            "featured_count": Product.objects.filter(is_active=True, is_featured=True).count(),
            "trending_count": Product.objects.filter(is_active=True, is_trending=True).count(),
            "low_stock_count": low_stock.count(),
            "recent_orders": orders[:8],
            "low_stock": low_stock[:8],
            "recent_products": Product.objects.order_by("-created_at")[:8],
            "recent_customers": User.objects.filter(profile__role="customer").order_by("-date_joined")[:8],
            "category_count": Category.objects.count(),
        },
    )


@never_cache
def orders(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    order_qs = Order.objects.select_related("customer").prefetch_related("items")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    payment = request.GET.get("payment", "").strip()
    date = request.GET.get("date", "").strip()
    if query:
        order_qs = order_qs.filter(
            Q(order_number__icontains=query)
            | Q(customer__username__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(customer__first_name__icontains=query)
            | Q(customer__last_name__icontains=query)
        )
    if status:
        order_qs = order_qs.filter(status=status)
    if payment:
        order_qs = order_qs.filter(payment_status=payment)
    if date:
        order_qs = order_qs.filter(created_at__date=date)
    return render(
        request,
        "dashboard/admin/orders.html",
        {
            "page_obj": paginate(request, order_qs, 15),
            "query": query,
            "status": status,
            "payment": payment,
            "date": date,
            "status_choices": Order.STATUS_CHOICES,
            "payment_choices": Order.PAYMENT_CHOICES,
        },
    )


@never_cache
def order_detail(request, order_number):
    blocked = require_admin(request)
    if blocked:
        return blocked
    order = get_object_or_404(Order.objects.select_related("customer", "shipping_address").prefetch_related("items"), order_number=order_number)
    form = OrderStatusForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Order status updated.")
        return redirect("admin_order_detail", order_number=order.order_number)
    return render(request, "dashboard/admin/order_detail.html", {"order": order, "form": form})


@never_cache
def products(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    product_qs = Product.objects.select_related("category").prefetch_related("images").order_by("name")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    active = request.GET.get("active", "").strip()
    featured = request.GET.get("featured", "").strip()
    trending = request.GET.get("trending", "").strip()
    if query:
        product_qs = product_qs.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if category:
        product_qs = product_qs.filter(category__slug=category)
    if active in {"1", "0"}:
        product_qs = product_qs.filter(is_active=active == "1")
    if featured == "1":
        product_qs = product_qs.filter(is_featured=True)
    if trending == "1":
        product_qs = product_qs.filter(is_trending=True)
    return render(
        request,
        "dashboard/admin/products.html",
        {
            "page_obj": paginate(request, product_qs, 15),
            "categories": Category.objects.filter(is_active=True),
            "query": query,
            "selected_category": category,
            "active": active,
            "featured": featured,
            "trending": trending,
        },
    )


@never_cache
def reviews(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    review_qs = ProductReview.objects.select_related("product", "customer").order_by("-created_at")
    return render(request, "dashboard/admin/reviews.html", {"page_obj": paginate(request, review_qs, 20)})


@never_cache
def review_delete(request, review_id):
    blocked = require_admin(request)
    if blocked:
        return blocked
    review = get_object_or_404(ProductReview, pk=review_id)
    if request.method == "POST":
        review.delete()
        messages.success(request, "Review deleted.")
    return redirect("admin_reviews")


def save_product_images(product, files):
    existing_count = product.images.filter(variant__isnull=True).count()
    incoming = files.getlist("images") if hasattr(files, "getlist") else []
    if existing_count + len(incoming) > 4:
        raise ValueError("A product can have a maximum of 4 images.")
    for index, image in enumerate(incoming, start=existing_count):
        product_image = ProductImage(product=product, image=image, alt_text=product.name, sort_order=index, is_primary=existing_count == 0 and index == 0, variant=None)
        product_image.full_clean()
        product_image.save()


@never_cache
def product_form(request, product_id=None, staff_portal=False):
    blocked = require_staff(request) if staff_portal else require_admin(request)
    if blocked:
        return blocked
    product = get_object_or_404(Product, pk=product_id) if product_id else None
    form = ProductManageForm(request.POST or None, request.FILES or None, instance=product)
    variant_formset = ProductVariantFormSet(request.POST or None, request.FILES or None, instance=product, prefix="variants")
    variant_formset.variant_type = (request.POST.get("variant_type") if request.method == "POST" else (product.variant_type if product else "none")) or "none"
    variant_formset.base_value = ""
    if variant_formset.variant_type == Product.VARIANT_SIZE:
        variant_formset.base_value = (request.POST.get("size") if request.method == "POST" else getattr(product, "size", "")) or ""
    elif variant_formset.variant_type == Product.VARIANT_COLOR:
        variant_formset.base_value = (request.POST.get("colour") if request.method == "POST" else getattr(product, "colour", "")) or ""
    if request.method == "POST" and form.is_valid():
        variant_formset.variant_type = form.cleaned_data.get("variant_type", "none")
        variant_formset.instance.has_variants = variant_formset.variant_type != "none"
    if request.method == "POST" and form.is_valid() and variant_formset.is_valid():
        try:
            with transaction.atomic():
                product = form.save()
                variant_formset.instance = product
                InventoryRecord.objects.update_or_create(
                    product=product,
                    defaults={
                        "current_stock": form.cleaned_data.get("stock") or 0,
                        "low_stock_threshold": form.cleaned_data.get("low_stock_threshold") or 5,
                    },
                )
                save_product_images(product, request.FILES)
                protected_variants = []
                for variant_form in variant_formset.forms:
                    if variant_form.cleaned_data.get("DELETE") and variant_form.instance.pk and OrderItem.objects.filter(variant=variant_form.instance).exists():
                        variant_form.cleaned_data["DELETE"] = False
                        variant_form.instance.is_active = False
                        protected_variants.append(variant_form.instance)
                variants = variant_formset.save()
                for variant in protected_variants:
                    variant.save(update_fields=["is_active"])
                for index, variant_form in enumerate(variant_formset.forms):
                    if variant_form.cleaned_data.get("DELETE") or not variant_form.instance.pk:
                        continue
                    variant = variant_form.instance
                    variant.variant_type = product.variant_type
                    variant.name = variant.colour if product.variant_type == Product.VARIANT_COLOR else variant.size
                    if product.variant_type == Product.VARIANT_COLOR:
                        variant.size = ""
                    else:
                        variant.colour = ""
                    update_fields = ["variant_type", "name", "size", "colour"]
                    if hasattr(variant, "updated_at"):
                        update_fields.append("updated_at")
                    variant.save(update_fields=update_fields)
                    images = request.FILES.getlist(f"variant_images_{index}")
                    existing_count = variant.images.count()
                    if existing_count + len(images) > 4:
                        raise ValueError("Each variant can have a maximum of 4 images.")
                    for image_index, image in enumerate(images, start=existing_count):
                        product_image = ProductImage(product=product, variant=variant, image=image, alt_text=f"{product.name} - {variant.name}", sort_order=image_index, is_primary=existing_count == 0 and image_index == 0)
                        product_image.full_clean()
                        product_image.save()
            messages.success(request, "Product updated successfully." if product_id else "Product created successfully.")
            return redirect("employee_products" if staff_portal else "admin_products")
        except (ValueError, ValidationError) as error:
            form.add_error(None, str(error))
    subcategory_options = {}
    subcategories = Category.objects.filter(is_active=True, parent__isnull=False).select_related("parent").order_by(
        "parent__sort_order", "sort_order", "name"
    )
    for subcategory in subcategories:
        subcategory_options.setdefault(str(subcategory.parent_id), []).append({"id": subcategory.id, "name": subcategory.name})
    return render(
        request,
        "dashboard/admin/product_form.html",
        {
            "form": form,
            "product": product,
            "variant_formset": variant_formset,
            "base_image_count": product.images.filter(variant__isnull=True).count() if product else 0,
            "subcategory_options_json": json.dumps(subcategory_options, cls=DjangoJSONEncoder),
            "staff_portal": staff_portal,
            "form_action_url": reverse(
                "employee_product_edit" if staff_portal and product else
                "employee_product_add" if staff_portal else
                "admin_product_edit" if product else "admin_product_add",
                args=[product.id] if product else [],
            ),
        },
    )


@never_cache
def product_image_delete(request, product_id, image_id, staff_portal=False):
    blocked = require_staff(request) if staff_portal else require_admin(request)
    if blocked:
        return blocked
    if request.method != "POST":
        return redirect("employee_product_edit" if staff_portal else "admin_product_edit", product_id=product_id)
    image = get_object_or_404(ProductImage, pk=image_id, product_id=product_id)
    image.delete()
    messages.success(request, "Product image removed.")
    return redirect("employee_product_edit" if staff_portal else "admin_product_edit", product_id=product_id)


@never_cache
def product_toggle(request, product_id, staff_portal=False):
    blocked = require_staff(request) if staff_portal else require_admin(request)
    if blocked:
        return blocked
    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        product.is_active = not product.is_active
        product.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{product.name} was {'activated' if product.is_active else 'deactivated'} successfully.")
    return redirect("employee_products" if staff_portal else "admin_products")


@never_cache
def product_delete(request, product_id):
    blocked = require_admin(request)
    if blocked:
        return blocked
    product = get_object_or_404(Product, pk=product_id)
    if request.method != "POST":
        return redirect("admin_products")
    if OrderItem.objects.filter(product=product).exists():
        messages.error(request, "This product is referenced by existing orders and cannot be permanently deleted. Deactivate it instead.")
        return redirect("admin_products")
    with transaction.atomic():
        product.delete()
    messages.success(request, f"{product.name} was deleted successfully.")
    return redirect("admin_products")


@never_cache
def categories(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    category_qs = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related("children").annotate(product_count=Count("products")).order_by("sort_order", "name")
    query = request.GET.get("q", "").strip()
    if query:
        category_qs = category_qs.filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(children__name__icontains=query)).distinct()
    return render(request, "dashboard/admin/categories.html", {"categories": category_qs, "query": query})


@never_cache
def category_form(request, category_id=None):
    blocked = require_admin(request)
    if blocked:
        return blocked
    category = get_object_or_404(Category, pk=category_id) if category_id else None
    form = CategoryNameForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated successfully." if category else "Category added successfully.")
        return redirect("admin_categories")
    return render(request, "dashboard/admin/category_form.html", {"form": form, "category": category, "parent_category": category.parent if category else None})


@never_cache
def subcategory_form(request, category_id, subcategory_id=None):
    blocked = require_admin(request)
    if blocked:
        return blocked
    parent = get_object_or_404(Category, pk=category_id, parent__isnull=True)
    subcategory = get_object_or_404(Category, pk=subcategory_id, parent=parent) if subcategory_id else None
    form = CategoryNameForm(request.POST or None, instance=subcategory, parent=parent)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Subcategory updated successfully." if subcategory else "Subcategory added successfully.")
        return redirect("admin_categories")
    return render(request, "dashboard/admin/category_form.html", {"form": form, "category": subcategory, "parent_category": parent, "is_subcategory": True})


@never_cache
def inventory(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    records = InventoryRecord.objects.select_related("product", "variant").order_by("product__name")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        records = records.filter(Q(product__name__icontains=query) | Q(product__sku__icontains=query) | Q(variant__sku__icontains=query))
    if status == "low":
        records = records.filter(current_stock__gt=0, current_stock__lte=5)
    elif status == "out":
        records = records.filter(current_stock__lte=0)
    return render(request, "dashboard/admin/inventory.html", {"page_obj": paginate(request, records, 15), "query": query, "status": status})


@never_cache
def inventory_edit(request, record_id):
    blocked = require_admin(request)
    if blocked:
        return blocked
    record = get_object_or_404(InventoryRecord.objects.select_related("product", "variant"), pk=record_id)
    old_stock = record.current_stock
    form = InventoryUpdateForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        delta = record.current_stock - old_stock
        if delta:
            StockMovement.objects.create(inventory=record, movement_type=StockMovement.ADJUSTMENT, quantity=delta, created_by=request.user, note=form.cleaned_data.get("note", ""))
        messages.success(request, "Inventory updated.")
        return redirect("admin_inventory")
    return render(request, "dashboard/admin/inventory_form.html", {"form": form, "record": record})


@never_cache
def featured_products(request):
    return product_flag_page(request, "featured")


@never_cache
def trending_materials(request):
    return product_flag_page(request, "trending")


def product_flag_page(request, mode):
    blocked = require_admin(request)
    if blocked:
        return blocked
    field = "is_featured" if mode == "featured" else "is_trending"
    order_field = "featured_order" if mode == "featured" else "trending_order"
    if request.method == "POST":
        product = get_object_or_404(Product, pk=request.POST.get("product_id"))
        action = request.POST.get("action")
        if action == "add":
            setattr(product, field, True)
        elif action == "remove":
            setattr(product, field, False)
        product.save(update_fields=[field, "updated_at"])
        return redirect("admin_featured_products" if mode == "featured" else "admin_trending_materials")
    selected = Product.objects.filter(is_active=True, **{field: True}).order_by(order_field, "name")
    available = Product.objects.filter(is_active=True, **{field: False}).order_by("name")[:20]
    return render(request, "dashboard/admin/product_flag.html", {"mode": mode, "selected": selected, "available": available})


@never_cache
def customers(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    qs = User.objects.filter(profile__role=UserProfile.CUSTOMER).annotate(order_count=Count("orders"), total_spend=Sum("orders__grand_total")).order_by("-date_joined")
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(username__icontains=query) | Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(profile__phone__icontains=query))
    return render(request, "dashboard/admin/customers.html", {"page_obj": paginate(request, qs, 15), "query": query})


@never_cache
def customer_detail(request, customer_id):
    blocked = require_admin(request)
    if blocked:
        return blocked
    customer = get_object_or_404(User.objects.select_related("profile"), pk=customer_id, profile__role=UserProfile.CUSTOMER)
    orders = Order.objects.filter(customer=customer)
    return render(request, "dashboard/admin/customer_detail.html", {"customer": customer, "orders": orders[:20], "total_spend": orders.aggregate(total=Sum("grand_total"))["total"] or 0})


@never_cache
def employees(request):
    return people_list(request, UserProfile.STAFF, "dashboard/admin/employees.html")


@never_cache
def employee_form(request, user_id=None):
    return people_form(request, EmployeeManageForm, UserProfile.STAFF, "dashboard/admin/employee_form.html", "admin_employees", user_id)


@never_cache
def employee_remove(request, user_id):
    blocked = require_admin(request)
    if blocked:
        return blocked
    employee = get_object_or_404(User.objects.select_related("profile"), pk=user_id, profile__role=UserProfile.STAFF)
    if request.method != "POST":
        return redirect("admin_employees")
    if employee.pk == request.user.pk:
        messages.error(request, "You cannot remove your own account.")
        return redirect("admin_employees")
    employee.is_active = False
    employee.save(update_fields=["is_active"])
    messages.success(request, "Employee account removed successfully.")
    return redirect("admin_employees")


@never_cache
def agents(request):
    return people_list(request, UserProfile.AGENT, "dashboard/admin/agents.html")


@never_cache
def agent_form(request, user_id=None):
    return people_form(request, AgentManageForm, UserProfile.AGENT, "dashboard/admin/agent_form.html", "admin_agents", user_id)


def people_list(request, role, template):
    blocked = require_admin(request)
    if blocked:
        return blocked
    qs = User.objects.filter(profile__role=role).select_related("profile")
    if role == UserProfile.AGENT:
        qs = qs.select_related("agent_profile")
    qs = qs.order_by("first_name", "username")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        qs = qs.filter(Q(username__icontains=query) | Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(profile__phone__icontains=query))
        if role == UserProfile.AGENT:
            qs = qs | User.objects.filter(profile__role=role, agent_profile__agent_code__icontains=query).select_related("profile", "agent_profile")
    if status in {"active", "inactive"}:
        qs = qs.filter(is_active=status == "active")
    qs = qs.distinct()
    return render(request, template, {"page_obj": paginate(request, qs, 15), "query": query, "status": status})


def people_form(request, form_class, role, template, redirect_name, user_id=None):
    blocked = require_admin(request)
    if blocked:
        return blocked
    user = get_object_or_404(User, pk=user_id, profile__role=role) if user_id else None
    form = form_class(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save(created_by=request.user)
        messages.success(request, "Account saved.")
        return redirect(redirect_name)
    return render(request, template, {"form": form, "managed_user": user})


@never_cache
def analytics(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    orders_qs = Order.objects.all()
    paid = orders_qs.filter(payment_status="paid").exclude(status="cancelled")
    revenue = paid.aggregate(total=Sum("grand_total"))["total"] or 0
    products_sold = OrderItem.objects.filter(order__in=paid).aggregate(total=Sum("quantity"))["total"] or 0
    avg_order = revenue / paid.count() if paid.count() else 0
    top_products = OrderItem.objects.values("product_name").annotate(quantity=Sum("quantity"), revenue=Sum("line_total")).order_by("-quantity")[:8]
    status_breakdown = orders_qs.values("status").annotate(count=Count("id")).order_by("status")
    return render(request, "dashboard/admin/analytics.html", {"revenue": revenue, "orders_count": orders_qs.count(), "avg_order": avg_order, "products_sold": products_sold, "top_products": top_products, "status_breakdown": status_breakdown})


@never_cache
def settings(request):
    blocked = require_admin(request)
    if blocked:
        return blocked
    return render(request, "dashboard/admin/settings.html")
