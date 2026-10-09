from django.db import migrations


def copy_modular_furniture(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    ServiceCategory = apps.get_model("services", "ServiceCategory")
    parent = Category.objects.filter(slug="modular-furniture", parent__isnull=True).first()
    if not parent:
        return
    service_parent, _ = ServiceCategory.objects.get_or_create(slug=parent.slug, defaults={"name": parent.name, "description": parent.description, "sort_order": parent.sort_order})
    for child in Category.objects.filter(parent=parent):
        ServiceCategory.objects.get_or_create(slug=child.slug, defaults={"name": child.name, "description": child.description, "parent": service_parent, "sort_order": child.sort_order})


class Migration(migrations.Migration):
    dependencies = [("services", "0001_initial"), ("catalog", "0012_product_gst_rate_productvariant_gst_rate")]
    operations = [migrations.RunPython(copy_modular_furniture, migrations.RunPython.noop)]
