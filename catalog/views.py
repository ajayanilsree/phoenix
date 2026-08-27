from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product


CATALOG_LABELS = {
    "boards-panels": "Boards & Panels",
    "pvc-foamboards": "PVC Foamboards",
    "wpc-foamboards": "WPC Foamboards",
    "charcoal-louvers": "Charcoal Louvers",
    "wpc-panels": "WPC Panels",
    "bamboo-charcoal-panels": "Bamboo Charcoal Panels",
    "kitchen-fittings-accessories": "Kitchen Fittings & Accessories",
    "wire-baskets": "Wire Baskets",
    "drawer-system": "Drawer System",
    "hinges": "Hinges",
    "telescopic-channels": "Telescopic Channels",
    "pantry-units": "Pantry Units",
    "corner-units": "Corner Units",
    "pull-system": "Pull & System",
    "wardrobe-bed-fittings": "Wardrobe & Bed Fittings",
    "sliding-door-fittings": "Sliding Door Fittings",
    "wardrobe-accessories": "Wardrobe Accessories",
    "cabinet-handles-knob": "Cabinet Handles & Knob",
    "bed-fitting": "Bed Fitting",
    "furniture-lights": "Furniture Lights",
    "modular-furniture": "Modular Furniture",
    "modular-kitchen": "Modular Kitchen",
    "wardrobe": "Wardrobe",
    "tv-unit": "TV Unit",
    "table-top-wash-basin": "Table Top Wash Basin",
    "bed-with-bed-rest": "Bed with Bed Rest",
    "dressing-unit": "Dressing Unit",
    "customised-sofas": "Customised Sofas",
    "prayer-unit": "Prayer Unit",
    "partition-walls": "Partition Walls",
    "recliner": "Recliner",
    "dining-table": "Dining Table",
    "wall-panelling": "Wall Panelling",
    "others": "Others",
    "g-profiles": "G Profiles",
    "glass-shutter-profiles": "Glass Shutter Profiles",
    "general-hardware": "General Hardware",
    "adhesives": "Adhesives",
    "door-window-fittings": "Door & Window Fittings",
    "home-decor": "Home Decor",
    "space-saving-furniture": "Space Saving Furniture",
    "tools": "Tools",
    "indoor-plants": "Indoor Plants",
}


def product_queryset():
    return Product.objects.filter(is_active=True).select_related("category", "subcategory").prefetch_related("images", "variants")


def shop(request, main_slug=None, sub_slug=None):
    products = product_queryset()
    categories = Category.objects.filter(is_active=True)
    query = request.GET.get("q", "").strip()
    catalogue_query = CATALOG_LABELS.get(sub_slug or main_slug, "")
    if catalogue_query and not query:
        query = catalogue_query
    category_slug = request.GET.get("category", "").strip()
    availability = request.GET.get("availability", "").strip()
    sort = request.GET.get("sort", "recommended")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(short_description__icontains=query)
            | Q(full_description__icontains=query)
            | Q(category__name__icontains=query)
        )
    if category_slug:
        products = products.filter(Q(category__slug=category_slug) | Q(subcategory__slug=category_slug))
    if availability == "in_stock":
        products = products.filter(inventory__current_stock__gt=0)

    ordering = {
        "newest": "-created_at",
        "price_low": "price",
        "price_high": "-price",
        "name": "name",
        "recommended": "-is_featured",
    }.get(sort, "-is_featured")
    products = products.order_by(ordering, "name")

    paginator = Paginator(products, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "catalog/shop.html",
        {
            "page_obj": page,
            "categories": categories,
            "query": query,
            "selected_category": category_slug,
            "availability": availability,
            "sort": sort,
            "catalogue_query": catalogue_query,
        },
    )


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    request.GET = request.GET.copy()
    request.GET["category"] = slug
    response = shop(request)
    response.context_data = getattr(response, "context_data", {})
    return response


def product_detail(request, slug):
    product = get_object_or_404(product_queryset(), slug=slug)
    related = product_queryset().filter(category=product.category).exclude(id=product.id)[:4]
    return render(request, "catalog/product_detail.html", {"product": product, "related_products": related})
