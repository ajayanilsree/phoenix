from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ChatbotFAQ",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.CharField(max_length=220)),
                ("answer", models.TextField()),
                ("keywords", models.CharField(blank=True, help_text="Comma-separated keywords that should match this FAQ.", max_length=300)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Chatbot FAQ",
                "verbose_name_plural": "Chatbot FAQs",
                "ordering": ["display_order", "question"],
            },
        ),
    ]
