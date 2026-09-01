from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Avg, Count, Q
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
import json

from accounts.decorators import user_role
from .forms import ProductReviewForm
from .models import Category, Product, ProductReview


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
    category = None
    subcategory = None
    if main_slug:
        category = get_object_or_404(Category, slug=main_slug, is_active=True, parent__isnull=True)
        if sub_slug:
            subcategory = get_object_or_404(
                Category,
                slug=sub_slug,
                parent=category,
                is_active=True,
            )
        products = products.filter(category=category)
        if subcategory:
            products = products.filter(subcategory=subcategory)

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
    variants = list(product.variants.filter(is_active=True).prefetch_related("images"))
    variant_data = [
        {
            "id": variant.id,
            "name": variant.name,
            "sku": variant.sku,
            "size": variant.size,
            "colour": variant.colour,
            "thickness": variant.thickness,
            "finish": variant.finish,
            "price": str(variant.price),
            "compare_price": str(variant.compare_price) if variant.compare_price else "",
            "discount_percent": variant.discount_percent or 0,
            "stock": variant.stock,
            "images": [{"url": image.image.url, "alt": image.alt_text or product.name} for image in variant.images.all() if image.image],
        }
        for variant in variants
    ]
    base_image_data = [
        {"url": image.image.url, "alt": image.alt_text or product.name}
        for image in product.images.filter(variant__isnull=True)
        if image.image
    ]
    base_inventory = getattr(product, "inventory", None)
    base_option = {
        "id": "base",
        "option_type": "base",
        "sku": product.sku,
        "size": product.size,
        "colour": product.colour,
        "price": str(product.price),
        "compare_price": str(product.compare_at_price) if product.compare_at_price else "",
        "discount_percent": product.discount_percent or 0,
        "stock": base_inventory.current_stock if base_inventory else 0,
        "images": base_image_data,
    }
    reviews = product.reviews.select_related("customer").all()[:10]
    review_summary = product.reviews.aggregate(average=Avg("rating"), count=Count("id"))
    own_review = None
    review_form = None
    if request.user.is_authenticated and user_role(request.user) == "customer":
        own_review = product.reviews.filter(customer=request.user).first()
        review_form = ProductReviewForm(instance=own_review)
    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "related_products": related,
            "reviews": reviews,
            "review_average": review_summary["average"],
            "review_count": review_summary["count"],
            "own_review": own_review,
            "review_form": review_form,
            "variants": variants,
            "variant_data_json": json.dumps(variant_data, cls=DjangoJSONEncoder),
            "base_option_data_json": json.dumps(base_option, cls=DjangoJSONEncoder),
            "base_image_data_json": json.dumps(base_image_data, cls=DjangoJSONEncoder),
        },
    )


@login_required
def product_review(request, slug):
    if user_role(request.user) != "customer":
        raise PermissionDenied
    if request.method != "POST":
        return redirect("product_detail", slug=slug)
    product = get_object_or_404(Product.objects.filter(is_active=True), slug=slug)
    existing = ProductReview.objects.filter(product=product, customer=request.user).first()
    form = ProductReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.customer = request.user
        review.save()
        messages.success(request, "Thank you for your review.")
        return redirect(f"{product.get_absolute_url()}#reviews")
    messages.error(request, "Please correct the review form and try again.")
    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "related_products": product_queryset().filter(category=product.category).exclude(id=product.id)[:4],
            "reviews": product.reviews.select_related("customer").all()[:10],
            "review_average": product.reviews.aggregate(average=Avg("rating"))["average"],
            "review_count": product.reviews.count(),
            "own_review": existing,
            "review_form": form,
        },
    )
