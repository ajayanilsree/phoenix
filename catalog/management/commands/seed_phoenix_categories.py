from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Product


CATALOGUE = [
    (
        "Boards & Panels",
        [
            "PVC Foamboards",
            "WPC Foamboards",
            "Charcoal Louvers",
            "WPC Panels",
            "Bamboo Charcoal Panels",
        ],
    ),
    (
        "Kitchen Fittings & Accessories",
        [
            "Wire Baskets",
            "Drawer System",
            "Hinges",
            "Telescopic Channels",
            "Pantry Units",
            "Corner Units",
            "Pull & System",
        ],
    ),
    (
        "Wardrobe & Bed Fittings",
        [
            "Sliding Door Fittings",
            "Wardrobe Accessories",
            "Cabinet Handles & Knob",
            "Bed Fitting",
            "Furniture Lights",
        ],
    ),
    (
        "Modular Furniture",
        [
            "Modular Kitchen",
            "Wardrobe",
            "TV Unit",
            "Table Top Wash Basin",
            "Bed with Bed Rest",
            "Dressing Unit",
            "Customised Sofas",
            "Prayer Unit",
            "Partition Walls",
            "Recliner",
            "Dining Table",
            "Wall Panelling",
        ],
    ),
    (
        "Others",
        [
            "G Profiles",
            "Glass Shutter Profiles",
            "General Hardware",
            "Adhesives",
            "Door & Window Fittings",
            "Home Decor",
            "Space Saving Furniture",
            "Tools",
            "Indoor Plants",
        ],
    ),
]

PRODUCT_CATEGORY_MAP = {
    "wall-panels": ("boards-panels", "wpc-panels"),
    "wpc-pvc-boards": ("boards-panels", None),
    "wpcpvc-boards": ("boards-panels", None),
    "pvc-foamboards": ("boards-panels", "pvc-foamboards"),
    "wpc-foamboards": ("boards-panels", "wpc-foamboards"),
    "charcoal-louvers": ("boards-panels", "charcoal-louvers"),
    "wpc-panels": ("boards-panels", "wpc-panels"),
    "bamboo-charcoal": ("boards-panels", "bamboo-charcoal-panels"),
    "bamboo-charcoal-panels": ("boards-panels", "bamboo-charcoal-panels"),
    "uv-marble-sheets": ("boards-panels", None),
    "kitchen-accessories": ("kitchen-fittings-accessories", None),
    "kitchen-fittings-accessories": ("kitchen-fittings-accessories", None),
    "cabinet-handles": ("wardrobe-bed-fittings", "cabinet-handles-knob"),
    "cabinet-handles-knob": ("wardrobe-bed-fittings", "cabinet-handles-knob"),
}


class Command(BaseCommand):
    help = "Seed the Phoenix Interior Hub category hierarchy without duplicating rows."

    @transaction.atomic
    def handle(self, *args, **options):
        allowed_ids = set()
        by_slug = {}

        for main_index, (main_name, children) in enumerate(CATALOGUE):
            main_slug = slugify(main_name)
            main, _ = Category.objects.update_or_create(
                slug=main_slug,
                defaults={
                    "name": main_name,
                    "parent": None,
                    "is_active": True,
                    "sort_order": main_index,
                },
            )
            allowed_ids.add(main.id)
            by_slug[main_slug] = main
            for child_index, child_name in enumerate(children):
                child_slug = slugify(child_name)
                child, _ = Category.objects.update_or_create(
                    slug=child_slug,
                    defaults={
                        "name": child_name,
                        "parent": main,
                        "is_active": True,
                        "sort_order": child_index,
                    },
                )
                allowed_ids.add(child.id)
                by_slug[child_slug] = child

        remapped = 0
        for product in Product.objects.select_related("category", "subcategory"):
            current_slug = product.subcategory.slug if product.subcategory else product.category.slug
            main_slug, sub_slug = PRODUCT_CATEGORY_MAP.get(current_slug, PRODUCT_CATEGORY_MAP.get(product.category.slug, (None, None)))
            if not main_slug:
                continue
            main = by_slug.get(main_slug)
            sub = by_slug.get(sub_slug) if sub_slug else None
            if main and (product.category_id != main.id or product.subcategory_id != (sub.id if sub else None)):
                product.category = main
                product.subcategory = sub
                product.save(update_fields=["category", "subcategory", "updated_at"])
                remapped += 1

        Category.objects.exclude(id__in=allowed_ids).update(is_active=False)
        self.stdout.write(self.style.SUCCESS("Phoenix Interior Hub category hierarchy is ready."))
        self.stdout.write(f"Products remapped safely: {remapped}")
