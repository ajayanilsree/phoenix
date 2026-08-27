from django.db.models import Q
from django.urls import reverse

from catalog.models import Category, Product


CATALOGUE_GROUPS = {
    "boards-panels": {
        "name": "Boards & Panels",
        "children": {
            "pvc-foamboards": "PVC Foamboards",
            "wpc-foamboards": "WPC Foamboards",
            "charcoal-louvers": "Charcoal Louvers",
            "wpc-panels": "WPC Panels",
            "bamboo-charcoal-panels": "Bamboo Charcoal Panels",
        },
    },
    "kitchen-fittings-accessories": {
        "name": "Kitchen Fittings & Accessories",
        "children": {
            "wire-baskets": "Wire Baskets",
            "drawer-system": "Drawer System",
            "hinges": "Hinges",
            "telescopic-channels": "Telescopic Channels",
            "pantry-units": "Pantry Units",
            "corner-units": "Corner Units",
            "pull-system": "Pull & System",
        },
    },
    "wardrobe-bed-fittings": {
        "name": "Wardrobe & Bed Fittings",
        "children": {
            "sliding-door-fittings": "Sliding Door Fittings",
            "wardrobe-accessories": "Wardrobe Accessories",
            "cabinet-handles-knob": "Cabinet Handles & Knob",
            "bed-fitting": "Bed Fitting",
            "furniture-lights": "Furniture Lights",
        },
    },
    "modular-furniture": {
        "name": "Modular Furniture",
        "children": {
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
        },
    },
    "others": {
        "name": "Others",
        "children": {
            "g-profiles": "G Profiles",
            "glass-shutter-profiles": "Glass Shutter Profiles",
            "general-hardware": "General Hardware",
            "adhesives": "Adhesives",
            "door-window-fittings": "Door & Window Fittings",
            "home-decor": "Home Decor",
            "space-saving-furniture": "Space Saving Furniture",
            "tools": "Tools",
            "indoor-plants": "Indoor Plants",
        },
    },
}


def catalogue_category_actions(query):
    query = query.lower()
    actions = []
    for group_slug, group in CATALOGUE_GROUPS.items():
        group_name = group["name"]
        if group_name.lower() in query:
            actions.append({"label": f"Browse {group_name}", "url": reverse("shop_catalogue_main", kwargs={"main_slug": group_slug})})
        for child_slug, child_name in group["children"].items():
            if child_name.lower() in query or child_slug.replace("-", " ") in query:
                actions.append(
                    {
                        "label": f"View {child_name}",
                        "url": reverse("shop_catalogue_sub", kwargs={"main_slug": group_slug, "sub_slug": child_slug}),
                    }
                )
    return actions[:5]


def serialize_product(product):
    image_url = ""
    primary_image = product.primary_image
    if primary_image and primary_image.image:
        image_url = primary_image.image.url

    stock_status = "Contact for Availability"
    try:
        if product.inventory.current_stock <= 0:
            stock_status = "Out of Stock"
        elif product.inventory.current_stock <= product.inventory.low_stock_threshold:
            stock_status = "Low Stock"
        else:
            stock_status = "In Stock"
    except Product.inventory.RelatedObjectDoesNotExist:
        stock_status = "Contact for Availability"

    return {
        "id": product.id,
        "name": product.name,
        "url": product.get_absolute_url(),
        "image": image_url,
        "price": f"₹{product.price} / {product.get_unit_type_display()}",
        "availability": stock_status,
        "category": product.category.name if product.category else "",
        "subcategory": product.subcategory.name if product.subcategory else "",
        "summary": product.short_description,
    }


def find_relevant_catalogue_context(query, page_context=None, limit=8):
    query = (query or "").strip()
    page_context = page_context or {}
    products = Product.objects.filter(is_active=True).select_related("category", "subcategory").prefetch_related("images")

    context_product = None
    if page_context.get("type") == "product" and page_context.get("slug"):
        context_product = products.filter(slug=page_context["slug"]).first()

    filters = Q()
    if query:
        filters = (
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(short_description__icontains=query)
            | Q(full_description__icontains=query)
            | Q(features__icontains=query)
            | Q(applications__icontains=query)
            | Q(category__name__icontains=query)
            | Q(subcategory__name__icontains=query)
        )
        for token in [part for part in query.replace("/", " ").replace("&", " ").split() if len(part) > 2]:
            filters |= Q(name__icontains=token) | Q(category__name__icontains=token) | Q(subcategory__name__icontains=token)

    matched_products = list(products.filter(filters).distinct()[:limit]) if filters else []
    if context_product and context_product not in matched_products:
        matched_products.insert(0, context_product)

    active_categories = Category.objects.filter(is_active=True)
    category_matches = []
    if query:
        category_matches = list(active_categories.filter(Q(name__icontains=query) | Q(description__icontains=query)).distinct()[:5])

    actions = catalogue_category_actions(query)
    for category in category_matches:
        actions.append({"label": f"Browse {category.name}", "url": category.get_absolute_url()})

    return {
        "products": [serialize_product(product) for product in matched_products[:limit]],
        "categories": [{"id": category.id, "name": category.name, "url": category.get_absolute_url()} for category in category_matches],
        "actions": actions[:6],
    }
