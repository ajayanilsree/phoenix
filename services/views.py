import json
import re
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Q, Prefetch
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import user_role
from accounts.models import UserProfile
from orders.payment import get_razorpay_client
from orders.views import amount_in_paise

from .forms import ServiceCategoryForm, ServiceForm
from .link_previews import cache_preview
from .models import Service, ServiceBooking, ServiceCategory, ServiceImage
from .richtext import safe_link


def _dashboard_prefix(request):
    return "employee" if request.path.startswith("/employee/") or request.path.startswith("/staff/") else "admin"


def _route(request, admin_name, employee_name):
    return employee_name if _dashboard_prefix(request) == "employee" else admin_name


def _sidebar_template(request):
    return "dashboard/admin/_sidebar.html" if user_role(request.user) == UserProfile.ADMIN else "staff_portal/_sidebar.html"


def _staff_only(request):
    if not request.user.is_authenticated:
        return redirect("employee_login" if _dashboard_prefix(request) == "employee" else "phoenix_admin_login")
    required_role = UserProfile.STAFF if _dashboard_prefix(request) == "employee" else UserProfile.ADMIN
    if user_role(request.user) != required_role:
        raise PermissionDenied
    return None


def _service_category_options():
    roots = ServiceCategory.objects.filter(parent__isnull=True, is_active=True).prefetch_related(
        Prefetch("children", queryset=ServiceCategory.objects.filter(is_active=True).order_by("sort_order", "name"))
    ).order_by("sort_order", "name")
    return roots, {str(root.pk): [{"id": child.pk, "slug": child.slug, "name": child.name} for child in root.children.all()] for root in roots}


def _service_listing(request, category=None, subcategory=None):
    roots, child_options = _service_category_options()
    query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    selected_subcategory = request.GET.get("subcategory", "").strip()
    sort = request.GET.get("sort", "recommended").strip()

    if category is not None:
        selected_category = category.parent.slug if category.parent_id else category.slug
    if subcategory is not None:
        selected_subcategory = subcategory.slug

    services = Service.objects.filter(is_active=True).select_related("category", "subcategory").prefetch_related("images")
    if query:
        services = services.filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()
    if selected_category:
        services = services.filter(Q(category__slug=selected_category) | Q(category__parent__slug=selected_category))
    if selected_subcategory:
        services = services.filter(subcategory__slug=selected_subcategory)
    services = services.order_by({
        "name_asc": "title", "name_desc": "-title", "fee_low": "consultation_fee",
        "fee_high": "-consultation_fee", "newest": "-created_at", "recommended": "-created_at",
    }.get(sort, "-created_at"), "title")

    page = Paginator(services, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params["category"] = selected_category
    params["subcategory"] = selected_subcategory
    params["sort"] = sort

    def page_url(number):
        params["page"] = number
        return f"?{params.urlencode()}"

    total_pages = page.paginator.num_pages
    visible = set(range(1, min(total_pages, 5) + 1)) if page.number <= 3 else set(range(max(1, page.number - 2), min(total_pages, page.number + 2) + 1))
    visible.update({1, total_pages})
    pagination_items = []
    for number in sorted(visible):
        if pagination_items and number > pagination_items[-1]["number"] + 1:
            pagination_items.append({"type": "ellipsis"})
        pagination_items.append({"type": "page", "number": number, "url": page_url(number), "is_current": number == page.number})

    selected_root = next((root for root in roots if root.slug == selected_category), None)
    return render(request, "services/listing.html", {
        "page_obj": page, "categories": roots, "query": query, "selected_category": selected_category,
        "selected_subcategory": selected_subcategory, "sort": sort, "selected_root_id": selected_root.pk if selected_root else "",
        "subcategory_options_json": json.dumps(child_options), "pagination_items": pagination_items,
        "previous_page_url": page_url(page.previous_page_number) if page.has_previous() else "",
        "next_page_url": page_url(page.next_page_number) if page.has_next() else "",
        "listing_title": "Our Services" if category is None else category.name,
    })


def services_home(request):
    return _service_listing(request)


def service_category(request, slug):
    category = get_object_or_404(ServiceCategory.objects.select_related("parent"), slug=slug, is_active=True)
    return _service_listing(request, category.parent if category.parent_id else category, category if category.parent_id else None)


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.select_related("category", "category__parent", "subcategory", "subcategory__parent").prefetch_related("images"), slug=slug, is_active=True)
    return render(request, "services/detail.html", {"service": service})


@login_required
def book_service(request, slug):
    service = get_object_or_404(Service, slug=slug, is_active=True)
    if request.method == "POST":
        name = request.POST.get("customer_name", "").strip()
        email = request.POST.get("customer_email", "").strip()
        mobile = request.POST.get("customer_mobile", "").strip()
        if not name or not email or not mobile:
            return render(request, "services/book.html", {"service": service, "error": "Name, email and mobile number are required."})
        booking = ServiceBooking.objects.create(
            booking_reference=f"SVB{uuid.uuid4().hex[:12].upper()}", service=service,
            service_title_snapshot=service.title, consultation_fee_snapshot=service.consultation_fee,
            customer=request.user, customer_name=name, customer_email=email, customer_mobile=mobile,
            requirements=request.POST.get("requirements", "").strip(),
        )
        try:
            razorpay_order = get_razorpay_client().order.create({"amount": amount_in_paise(booking.consultation_fee_snapshot), "currency": "INR", "receipt": booking.booking_reference})
        except Exception:
            booking.payment_status = ServiceBooking.PAYMENT_FAILED
            booking.save(update_fields=["payment_status", "updated_at"])
            return render(request, "services/book.html", {"service": service, "error": "Online payment is temporarily unavailable. Please try again later."})
        booking.razorpay_order_id = razorpay_order["id"]
        booking.save(update_fields=["razorpay_order_id", "updated_at"])
        return render(request, "services/book.html", {"service": service, "booking": booking, "razorpay_options": {"key": settings.RAZORPAY_KEY_ID, "amount": amount_in_paise(booking.consultation_fee_snapshot), "currency": "INR", "name": "Phoenix Interior Hub", "description": booking.service_title_snapshot, "order_id": booking.razorpay_order_id, "prefill": {"name": name, "email": email, "contact": mobile}, "theme": {"color": "#0B3158"}}})
    return render(request, "services/book.html", {"service": service, "initial_name": request.user.get_full_name(), "initial_email": request.user.email})


@login_required
@require_POST
def verify_booking_payment(request, reference):
    with transaction.atomic():
        booking = get_object_or_404(ServiceBooking.objects.select_for_update(), booking_reference=reference, customer=request.user)
        payment_id = request.POST.get("razorpay_payment_id", "").strip()
        order_id = request.POST.get("razorpay_order_id", "").strip()
        signature = request.POST.get("razorpay_signature", "").strip()
        if booking.payment_status == ServiceBooking.PAYMENT_CONFIRMED:
            return JsonResponse({"success": True, "redirect_url": reverse("service_booking_confirmation", args=[booking.booking_reference])})
        if order_id != booking.razorpay_order_id or not payment_id or not signature:
            booking.payment_status = ServiceBooking.PAYMENT_PENDING
            booking.save(update_fields=["payment_status", "updated_at"])
            return JsonResponse({"success": False, "message": "Payment verification failed."}, status=400)
        try:
            client = get_razorpay_client()
            client.utility.verify_payment_signature({"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature})
            remote_order = client.order.fetch(order_id)
            if int(remote_order.get("amount", 0)) != amount_in_paise(booking.consultation_fee_snapshot) or remote_order.get("currency") != "INR":
                raise ValueError("Incorrect payment amount")
        except Exception:
            booking.payment_status = ServiceBooking.PAYMENT_PENDING
            booking.save(update_fields=["payment_status", "updated_at"])
            return JsonResponse({"success": False, "message": "Payment verification failed."}, status=400)
        booking.payment_status = ServiceBooking.PAYMENT_CONFIRMED
        booking.razorpay_payment_id = payment_id
        booking.razorpay_signature = signature
        booking.payment_confirmed_at = timezone.now()
        booking.save(update_fields=["payment_status", "razorpay_payment_id", "razorpay_signature", "payment_confirmed_at", "updated_at"])
    return JsonResponse({"success": True, "redirect_url": reverse("service_booking_confirmation", args=[booking.booking_reference])})


@login_required
def service_booking_confirmation(request, reference):
    booking = get_object_or_404(ServiceBooking, booking_reference=reference, customer=request.user)
    return render(request, "services/confirmation.html", {"booking": booking})


def _management_context(request, extra=None):
    service_children = ServiceCategory.objects.order_by("sort_order", "name")
    context = {
        "categories": ServiceCategory.objects.select_related("parent"),
        "service_category_tree": ServiceCategory.objects.filter(parent__isnull=True).annotate(subcategory_count=Count("children", filter=Q(children__is_active=True))).order_by("sort_order", "name").prefetch_related(Prefetch("children", queryset=service_children)),
        "services": Service.objects.select_related("category").prefetch_related("images"),
        "sidebar_template": _sidebar_template(request),
        "is_admin": user_role(request.user) == UserProfile.ADMIN,
    }
    if extra: context.update(extra)
    return context


def management_home(request):
    blocked = _staff_only(request)
    if blocked: return blocked
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    active = request.GET.get("active", "").strip()
    category_tree = ServiceCategory.objects.filter(parent__isnull=True).annotate(subcategory_count=Count("children", filter=Q(children__is_active=True)))
    if query:
        category_tree = category_tree.filter(Q(name__icontains=query) | Q(children__name__icontains=query)).distinct()
    context = _management_context(request, {"service_category_tree": category_tree.order_by("sort_order", "name").prefetch_related(Prefetch("children", queryset=ServiceCategory.objects.order_by("sort_order", "name"))), "query": query})
    return render(request, "services/management.html", context)


def category_form(request, category_id=None):
    blocked = _staff_only(request)
    if blocked: return blocked
    category = get_object_or_404(ServiceCategory, pk=category_id) if category_id else None
    form = ServiceCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_route(request, "admin_services", "employee_services"))
    return render(request, "services/category_form.html", {"form": form, "category": category, "sidebar_template": _sidebar_template(request), "is_subcategory": False, "is_admin": user_role(request.user) == UserProfile.ADMIN})


def service_subcategory_form(request, category_id, subcategory_id=None):
    blocked = _staff_only(request)
    if blocked:
        return blocked
    parent = get_object_or_404(ServiceCategory, pk=category_id, parent__isnull=True)
    category = get_object_or_404(ServiceCategory, pk=subcategory_id, parent=parent) if subcategory_id else None
    form = ServiceCategoryForm(request.POST or None, instance=category, parent=parent)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_route(request, "admin_services", "employee_services"))
    return render(request, "services/category_form.html", {"form": form, "category": category, "parent_category": parent, "sidebar_template": _sidebar_template(request), "is_subcategory": True, "is_admin": user_role(request.user) == UserProfile.ADMIN})


def service_form(request, service_id=None):
    blocked = _staff_only(request)
    if blocked: return blocked
    service = get_object_or_404(Service, pk=service_id) if service_id else None
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        images = request.FILES.getlist("images")
        remove_ids = {int(value) for value in request.POST.get("remove_image_ids", "").split(",") if value.strip().isdigit()}
        existing_images = service.images.all() if service else ServiceImage.objects.none()
        existing_count = existing_images.exclude(pk__in=remove_ids).count()
        if len(images) + existing_count > 4:
            form.add_error("title", "A service can have a maximum of four images.")
        else:
            invalid_image = next((image for image in images if image.size > 5 * 1024 * 1024 or image.content_type not in {"image/jpeg", "image/png", "image/webp"}), None)
            if invalid_image:
                form.add_error("title", f"{invalid_image.name} must be a JPEG, PNG or WebP image no larger than 5MB.")
            else:
                obj = form.save()
                for image_id in remove_ids:
                    ServiceImage.objects.filter(pk=image_id, service=obj).delete()
                for index, image in enumerate(images, start=obj.images.count()):
                    ServiceImage.objects.create(service=obj, image=image, sort_order=index)
                for url in re.findall(r'href=["\']([^"\']+)', obj.description):
                    if safe_link(url):
                        try:
                            cache_preview(url)
                        except Exception:
                            pass
                messages.success(request, f"{obj.title} was saved successfully.")
                return redirect(_route(request, "admin_services_list", "employee_services_list"))
    return render(request, "services/form.html", {"form": form, "service": service, "sidebar_template": _sidebar_template(request), "is_admin": user_role(request.user) == UserProfile.ADMIN, "subcategory_options_json": json.dumps(_subcategory_options())})


def _subcategory_options():
    categories = ServiceCategory.objects.filter(parent__isnull=True, is_active=True).prefetch_related(
        Prefetch("children", queryset=ServiceCategory.objects.filter(is_active=True).order_by("sort_order", "name"))
    )
    return {str(category.pk): [{"id": child.pk, "name": child.name} for child in category.children.all()] for category in categories}


def service_list(request):
    blocked = _staff_only(request)
    if blocked:
        return blocked
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    subcategory = request.GET.get("subcategory", "").strip()
    active = request.GET.get("active", "").strip()
    services = Service.objects.select_related("category", "subcategory").prefetch_related("images").order_by("-created_at", "-pk")
    if query:
        services = services.filter(Q(title__icontains=query) | Q(slug__icontains=query))
    if category.isdigit():
        services = services.filter(category_id=category)
    if subcategory.isdigit():
        services = services.filter(subcategory_id=subcategory)
    if active in {"1", "0"}:
        services = services.filter(is_active=active == "1")
    page_obj = Paginator(services, 15).get_page(request.GET.get("page"))
    return render(request, "services/list.html", {
        "page_obj": page_obj,
        "categories": ServiceCategory.objects.filter(parent__isnull=True, is_active=True).order_by("sort_order", "name"),
        "query": query,
        "selected_category": category,
        "selected_subcategory": subcategory,
        "active": active,
        "subcategory_options_json": json.dumps(_subcategory_options()),
        "sidebar_template": _sidebar_template(request),
        "is_admin": user_role(request.user) == UserProfile.ADMIN,
    })


def service_toggle(request, service_id):
    blocked = _staff_only(request)
    if blocked: return blocked
    if request.method != "POST": return redirect(_route(request, "admin_services_list", "employee_services_list"))
    service = get_object_or_404(Service, pk=service_id)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active", "updated_at"])
    return redirect(_route(request, "admin_services_list", "employee_services_list"))


def service_delete(request, service_id):
    blocked = _staff_only(request)
    if blocked: return blocked
    if request.method == "POST":
        service = get_object_or_404(Service, pk=service_id)
        if service.bookings.exists():
            messages.error(request, "A service with historical bookings cannot be deleted. Deactivate it instead.")
        else:
            service.delete()
    return redirect(_route(request, "admin_services_list", "employee_services_list"))


@require_POST
def category_delete(request, category_id):
    blocked = _staff_only(request)
    if blocked: return blocked
    category = get_object_or_404(ServiceCategory, pk=category_id)
    if category.children.exists():
        messages.error(request, f"{category.name} cannot be deleted because it contains subcategories. Delete those subcategories first.")
    elif category.services.exists():
        messages.error(request, f"{category.name} cannot be deleted because services are assigned to it. Remove or reassign those services first.")
    else:
        try:
            with transaction.atomic():
                category.delete()
            messages.success(request, f"{category.name} was deleted successfully.")
        except ProtectedError:
            messages.error(request, f"{category.name} cannot be deleted because existing records depend on it.")
    return redirect(_route(request, "admin_services", "employee_services"))


def service_image_delete(request, service_id, image_id):
    blocked = _staff_only(request)
    if blocked: return blocked
    if request.method == "POST":
        get_object_or_404(ServiceImage, pk=image_id, service_id=service_id).delete()
    return redirect(_route(request, "admin_service_list_edit", "employee_service_list_edit"), service_id=service_id)


def service_link_preview(request):
    url = safe_link(request.GET.get("url", ""))
    if not url:
        return JsonResponse({"error": "Invalid URL."}, status=400)
    try:
        preview = cache_preview(url)
    except Exception:
        preview = None
    if preview is None:
        return JsonResponse({"url": url, "title": url, "description": "", "image_url": "", "domain": ""})
    return JsonResponse({"url": url, "title": preview.title or url, "description": preview.description, "image_url": preview.image_url, "domain": preview.domain})


def service_orders(request):
    blocked = _staff_only(request)
    if blocked: return blocked
    query = request.GET.get("q", "").strip()
    payment = request.GET.get("payment", "").strip()
    status = request.GET.get("status", "").strip()
    bookings = ServiceBooking.objects.select_related("service").order_by("-created_at")
    if query: bookings = bookings.filter(Q(booking_reference__icontains=query) | Q(customer_name__icontains=query) | Q(customer_mobile__icontains=query) | Q(service_title_snapshot__icontains=query))
    if payment in dict(ServiceBooking.PAYMENT_STATUS_CHOICES): bookings = bookings.filter(payment_status=payment)
    if status in dict(ServiceBooking.SERVICE_STATUS_CHOICES): bookings = bookings.filter(service_status=status)
    return render(request, "services/orders.html", {"page_obj": Paginator(bookings, 15).get_page(request.GET.get("page")), "query": query, "payment": payment, "status": status, "sidebar_template": _sidebar_template(request)})


def service_order_detail(request, reference):
    blocked = _staff_only(request)
    if blocked: return blocked
    booking = get_object_or_404(ServiceBooking.objects.select_related("service", "service__category"), booking_reference=reference)
    if request.method == "POST":
        if booking.payment_status != ServiceBooking.PAYMENT_CONFIRMED:
            messages.error(request, "Only paid bookings can be completed.")
        else:
            booking.service_status = request.POST.get("service_status", ServiceBooking.PENDING)
            booking.save(update_fields=["service_status", "updated_at"])
            messages.success(request, "Service status updated.")
            return redirect(_route(request, "admin_service_order_detail", "employee_service_order_detail"), reference=reference)
    return render(request, "services/order_detail.html", {"booking": booking, "sidebar_template": _sidebar_template(request)})
