from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_agent_codes(apps, schema_editor):
    AgentProfile = apps.get_model("accounts", "AgentProfile")
    for index, profile in enumerate(AgentProfile.objects.filter(agent_code__isnull=True).order_by("id"), start=1):
        code = f"PHXAG{index:03d}"
        while AgentProfile.objects.filter(agent_code=code).exclude(pk=profile.pk).exists():
            index += 1
            code = f"PHXAG{index:03d}"
        profile.agent_code = code
        profile.save(update_fields=["agent_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="agentprofile",
            name="agent_code",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="agentprofile",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="agentprofile",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_agents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="agentprofile",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_staff",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(populate_agent_codes, migrations.RunPython.noop),
    ]
