from django.db import migrations, models


def infer_variant_types(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    for product in Product.objects.all():
        variants = ProductVariant.objects.filter(product=product)
        first = variants.first()
        if not first:
            continue
        variant_type = "color" if first.colour else "size" if first.size else "none"
        product.variant_type = variant_type
        product.has_variants = variant_type != "none"
        product.save(update_fields=["variant_type", "has_variants"])
        variants.update(variant_type=variant_type)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_product_variants_expanded")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="variant_type",
            field=models.CharField(
                choices=[("none", "None"), ("size", "Size"), ("color", "Color")],
                default="none",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="variant_type",
            field=models.CharField(
                choices=[("none", "None"), ("size", "Size"), ("color", "Color")],
                default="none",
                max_length=12,
            ),
        ),
        migrations.RunPython(infer_variant_types, migrations.RunPython.noop),
    ]
