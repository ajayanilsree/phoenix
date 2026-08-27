from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="featured_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="product",
            name="is_trending",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="trending_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
