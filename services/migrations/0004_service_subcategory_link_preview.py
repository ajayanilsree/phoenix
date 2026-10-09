from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("services", "0003_sync_modular_furniture_categories")]
    operations = [
        migrations.AddField(
            model_name="service",
            name="subcategory",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="subcategory_services", to="services.servicecategory"),
        ),
        migrations.CreateModel(
            name="ServiceLinkPreview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField(max_length=2048, unique=True)),
                ("title", models.CharField(blank=True, max_length=300)),
                ("description", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True, max_length=2048)),
                ("domain", models.CharField(blank=True, max_length=255)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
