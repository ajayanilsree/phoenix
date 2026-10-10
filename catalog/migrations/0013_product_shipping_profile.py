from django.db import migrations, models
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [("catalog", "0012_product_gst_rate_productvariant_gst_rate")]

    operations = [
        migrations.AddField(model_name="product", name="pickup_pincode", field=models.CharField(blank=True, max_length=6, validators=[django.core.validators.RegexValidator("^\\d{6}$", "Enter a valid 6-digit pickup PIN code.")]),),
        migrations.AddField(model_name="product", name="package_weight_kg", field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="product", name="package_length_cm", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="product", name="package_breadth_cm", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="product", name="package_height_cm", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="productvariant", name="pickup_pincode", field=models.CharField(blank=True, max_length=6, validators=[django.core.validators.RegexValidator("^\\d{6}$", "Enter a valid 6-digit pickup PIN code.")]),),
        migrations.AddField(model_name="productvariant", name="package_weight_kg", field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="productvariant", name="package_length_cm", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="productvariant", name="package_breadth_cm", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
        migrations.AddField(model_name="productvariant", name="package_height_cm", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"), "Enter a value greater than zero.")]),),
    ]
