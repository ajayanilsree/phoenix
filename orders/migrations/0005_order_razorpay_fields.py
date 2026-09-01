from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0004_address_types_and_billing"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_method",
            field=models.CharField(choices=[("razorpay", "Razorpay")], default="razorpay", max_length=30),
        ),
        migrations.AddField(
            model_name="order",
            name="razorpay_order_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="order",
            name="razorpay_payment_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="order",
            name="razorpay_signature",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
