import catalog.models
from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_product_trending_ordering"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productimage",
            name="image",
            field=models.ImageField(
                blank=True,
                upload_to="products/",
                validators=[
                    FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"]),
                    catalog.models.validate_product_image_size,
                ],
            ),
        ),
    ]
