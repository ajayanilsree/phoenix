import os
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFilter

from accounts.models import AgentProfile, StaffProfile, UserProfile
from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductVariant
from inventory.models import InventoryRecord


class Command(BaseCommand):
    help = "Create clearly labelled demo data for the Phoenix e-commerce platform."

    def create_demo_image(self, product, category_name):
        media_dir = Path(settings.MEDIA_ROOT) / "products" / "demo"
        media_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{product.slug}.jpg"
        file_path = media_dir / file_name

        width, height = 1200, 820
        image = Image.new("RGB", (width, height), "#f6f9fc")
        draw = ImageDraw.Draw(image)

        if "Marble" in category_name:
            image = Image.new("RGB", (width, height), "#f8f8f6")
            draw = ImageDraw.Draw(image)
            for offset in range(-200, width, 210):
                draw.line([(offset, 0), (offset + 520, height)], fill="#c9cfd6", width=8)
                draw.line([(offset + 42, 0), (offset + 560, height)], fill="#e0d6ce", width=3)
        elif "Louver" in category_name:
            image = Image.new("RGB", (width, height), "#3b241c")
            draw = ImageDraw.Draw(image)
            for x in range(0, width, 52):
                draw.rectangle([x, 0, x + 25, height], fill="#7a5746")
                draw.rectangle([x + 25, 0, x + 40, height], fill="#2f211b")
        elif "Bamboo" in category_name:
            image = Image.new("RGB", (width, height), "#d7c2ad")
            draw = ImageDraw.Draw(image)
            for y in range(0, height, 70):
                draw.rectangle([0, y, width, y + 34], fill="#b99d85")
                draw.line([(0, y + 34), (width, y + 34)], fill="#8f725e", width=3)
        elif "Wall" in category_name:
            image = Image.new("RGB", (width, height), "#e9dfd3")
            draw = ImageDraw.Draw(image)
            for x in range(0, width, 115):
                draw.rectangle([x, 0, x + 72, height], fill="#d0bba8")
                draw.line([(x + 72, 0), (x + 72, height)], fill="#a98d78", width=4)
        elif "Board" in category_name or "PVC" in category_name or "WPC" in category_name:
            image = Image.new("RGB", (width, height), "#edf3f7")
            draw = ImageDraw.Draw(image)
            for i, y in enumerate(range(70, height, 86)):
                fill = "#ffffff" if i % 2 == 0 else "#dfe9f0"
                draw.rounded_rectangle([120, y, width - 120, y + 46], radius=10, fill=fill, outline="#cdd9e2", width=2)
        else:
            image = Image.new("RGB", (width, height), "#eef4fa")
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle([180, 150, width - 180, height - 150], radius=28, fill="#ffffff", outline="#d5e0e8", width=6)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rectangle([0, height - 220, width, height], fill=(11, 49, 88, 34))
        odraw.rectangle([0, 0, width, height], outline=(221, 231, 239, 255), width=8)
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB").filter(ImageFilter.SMOOTH_MORE)
        image.save(file_path, "JPEG", quality=86, optimize=True)

        image_record, _ = ProductImage.objects.get_or_create(
            product=product,
            is_primary=True,
            defaults={"alt_text": product.name, "sort_order": 0},
        )
        image_record.image.name = f"products/demo/{file_name}"
        image_record.alt_text = product.name
        image_record.sort_order = 0
        image_record.save(update_fields=["image", "alt_text", "sort_order"])

    def handle(self, *args, **options):
        categories = [
            ("Wall Panels", "Decorative WPC and bamboo charcoal wall panels."),
            ("WPC/PVC Boards", "PVC and WPC foam boards for interior construction."),
            ("Bamboo Charcoal", "Warm textured bamboo charcoal panel surfaces."),
            ("UV Marble Sheets", "Marble-look decorative sheets for feature walls and TV units."),
            ("Charcoal Louvers", "Linear louver panels for bold modern surfaces."),
            ("Kitchen Accessories", "Modular kitchen and interior accessories."),
            ("Cabinet Handles", "Cabinet and furniture hardware accessories."),
        ]
        category_map = {}
        for index, (name, description) in enumerate(categories):
            category, _ = Category.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "description": description, "sort_order": index, "is_active": True},
            )
            category_map[name] = category

        products = [
            ("Charcoal Louvers Demo Panel", "PHX-CL-DEMO", "Charcoal Louvers", "panel", "8 ft x 5 in", "26 mm", "Walnut", "Fluted wood finish", "Charcoal louvers that bring bold style, premium texture and modern elegance to interior walls.", "Living rooms\nOffice receptions\nCommercial interiors"),
            ("WPC Wall Panel Demo Range", "PHX-WPC-WALL-DEMO", "Wall Panels", "panel", "9.5 ft x 6 in", "12 mm", "Natural Oak", "Matte texture", "WPC wall panels for modern elegance, durability and easy maintenance.", "Feature walls\nBedrooms\nLiving rooms"),
            ("UV Marble Sheet Demo", "PHX-UV-MS-DEMO", "UV Marble Sheets", "sheet", "8 ft x 4 ft", "3 mm", "White Carrara", "Gloss marble", "UV marble sheets for statement surfaces and TV units.", "TV units\nCommercial counters\nAccent walls"),
            ("Bamboo Charcoal Panel Demo", "PHX-BCP-DEMO", "Bamboo Charcoal", "sheet", "8 ft x 4 ft", "8 mm", "Warm Beige", "Fabric texture", "Bamboo charcoal panels with premium warmth and moisture-resistant performance.", "Bedrooms\nOffices\nHospitality interiors"),
            ("PVC Foam Board Demo", "PHX-PVC-FB-DEMO", "WPC/PVC Boards", "board", "8 ft x 4 ft", "18 mm", "White", "Smooth", "PVC foam boards for modular interior construction and decorative use.", "Cabinets\nPartitions\nInterior frameworks"),
            ("WPC Foam Board Demo", "PHX-WPC-FB-DEMO", "WPC/PVC Boards", "board", "8 ft x 4 ft", "17 mm", "Ivory", "Smooth", "WPC foam boards for sturdy and moisture-resistant interior applications.", "Furniture backing\nWall systems\nInterior construction"),
        ]
        for index, data in enumerate(products):
            name, sku, category, unit, size, thickness, colour, finish, description, applications = data
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "slug": slugify(name),
                    "category": category_map[category],
                    "short_description": description[:220],
                    "full_description": f"{description} Pricing is demo-only until Phoenix supplies approved commercial rates.",
                    "price": Decimal("100.00") + Decimal(index * 25),
                    "compare_at_price": None,
                    "unit_type": unit,
                    "size": size,
                    "thickness": thickness,
                    "colour": colour,
                    "finish": finish,
                    "specifications": {"Size": size, "Thickness": thickness, "Finish": finish, "Price status": "Demo only"},
                    "features": "Moisture-resistant\nLow maintenance\nPremium decorative finish",
                    "applications": applications,
                    "installation_notes": "Final installation guidance should be confirmed by Phoenix for each product range.",
                    "is_featured": index < 4,
                    "is_active": True,
                },
            )
            ProductVariant.objects.update_or_create(
                sku=f"{sku}-STD",
                product=product,
                defaults={"name": "Standard demo variant", "size": size, "thickness": thickness, "colour": colour, "finish": finish},
            )
            InventoryRecord.objects.update_or_create(
                product=product,
                defaults={"current_stock": 20 - index * 2, "low_stock_threshold": 5},
            )
            ProductAttribute.objects.update_or_create(product=product, name="Demo data", defaults={"value": "Requires client confirmation"})
            self.create_demo_image(product, category)

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            admin = User.objects.create_superuser("admin", "admin@phoenix.local")
            demo_admin_password = os.environ.get("PHOENIX_DEMO_ADMIN_PASSWORD")
            if demo_admin_password:
                admin.set_password(demo_admin_password)
            else:
                admin.set_unusable_password()
            admin.save(update_fields=["password"])
        admin.profile.role = UserProfile.ADMIN
        admin.profile.save(update_fields=["role"])

        agent, agent_created = User.objects.get_or_create(username="agent", defaults={"email": "agent@phoenix.local", "first_name": "Phoenix", "last_name": "Agent"})
        demo_agent_password = os.environ.get("PHOENIX_DEMO_AGENT_PASSWORD")
        if demo_agent_password:
            agent.set_password(demo_agent_password)
        elif agent_created:
            agent.set_unusable_password()
        agent.save()
        agent.profile.role = UserProfile.AGENT
        agent.profile.save(update_fields=["role"])
        AgentProfile.objects.get_or_create(user=agent, defaults={"territory": "Demo territory"})

        staff, staff_created = User.objects.get_or_create(username="staff", defaults={"email": "staff@phoenix.local", "first_name": "Phoenix", "last_name": "Staff"})
        demo_staff_password = os.environ.get("PHOENIX_DEMO_STAFF_PASSWORD")
        if demo_staff_password:
            staff.set_password(demo_staff_password)
        elif staff_created:
            staff.set_unusable_password()
        staff.is_staff = True
        staff.save()
        staff.profile.role = UserProfile.STAFF
        staff.profile.save(update_fields=["role"])
        StaffProfile.objects.get_or_create(user=staff, defaults={"department": "Operations", "can_update_stock": True})

        customer, customer_created = User.objects.get_or_create(username="customer", defaults={"email": "customer@phoenix.local", "first_name": "Demo", "last_name": "Customer"})
        demo_customer_password = os.environ.get("PHOENIX_DEMO_CUSTOMER_PASSWORD")
        if demo_customer_password:
            customer.set_password(demo_customer_password)
        elif customer_created:
            customer.set_unusable_password()
        customer.save()

        self.stdout.write(self.style.SUCCESS("Phoenix demo catalogue and role users are ready."))
