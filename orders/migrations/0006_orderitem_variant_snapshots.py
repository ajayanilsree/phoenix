from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0005_order_razorpay_fields")]

    operations = [
        migrations.AddField(model_name="orderitem", name="variant_sku", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="orderitem", name="variant_size", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="orderitem", name="variant_colour", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="orderitem", name="variant_thickness", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="orderitem", name="variant_finish", field=models.CharField(blank=True, max_length=100)),
    ]
