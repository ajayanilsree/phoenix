from django.shortcuts import render

from catalog.models import Category, Product


def home(request):
    categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by("sort_order", "name")[:5]
    featured_products = (
        Product.objects.filter(is_active=True, is_featured=True)
        .select_related("category")
        .prefetch_related("images")
        .order_by("featured_order", "-created_at")[:8]
    )
    trending_products = (
        Product.objects.filter(is_active=True, is_trending=True)
        .select_related("category")
        .prefetch_related("images")
        .order_by("trending_order", "-created_at")[:8]
    )
    applications = ["Living Room", "Kitchen", "Bedroom", "Office", "Commercial Interiors"]
    return render(
        request,
        "core/home.html",
        {
            "categories": categories,
            "featured_products": featured_products,
            "trending_products": trending_products,
            "applications": applications,
        },
    )


def about(request):
    return render(request, "core/about.html")


def page_not_found(request, exception=None):
    return render(request, "core/404.html", status=404)


def permission_denied(request, exception=None):
    return render(request, "core/403.html", status=403)
