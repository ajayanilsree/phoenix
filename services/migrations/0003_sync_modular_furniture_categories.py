from django.db import migrations


def sync_modular_furniture(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    ServiceCategory = apps.get_model("services", "ServiceCategory")
    source_parent = Category.objects.filter(slug="modular-furniture", parent__isnull=True).first()
    if not source_parent:
        return

    def copy_category(source, service_parent=None):
        service_category, _ = ServiceCategory.objects.update_or_create(
            slug=source.slug,
            defaults={
                "name": source.name,
                "description": source.description,
                "parent": service_parent,
                "is_active": True,
                "sort_order": source.sort_order,
            },
        )
        source.is_active = False
        source.save(update_fields=["is_active"])
        for child in Category.objects.filter(parent=source).order_by("sort_order", "name"):
            copy_category(child, service_category)

    copy_category(source_parent)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0012_product_gst_rate_productvariant_gst_rate"), ("services", "0002_seed_service_categories")]
    operations = [migrations.RunPython(sync_modular_furniture, migrations.RunPython.noop)]
