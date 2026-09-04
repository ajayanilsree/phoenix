from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_productvariant_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="description",
            field=models.TextField(blank=True),
        ),
    ]
