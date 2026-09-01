from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_productreview")]

    operations = [
        migrations.AddField(model_name="product", name="has_variants", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="productvariant", name="original_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="productvariant", name="selling_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="productvariant", name="stock", field=models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)])),
        migrations.AddField(model_name="productvariant", name="low_stock_threshold", field=models.PositiveIntegerField(default=5)),
        migrations.AddField(model_name="productimage", name="variant", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="images", to="catalog.productvariant")),
    ]
