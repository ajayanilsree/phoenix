from django.db import migrations, models
import django.db.models.deletion


def copy_legacy_addresses_to_delivery(apps, schema_editor):
    Address = apps.get_model("orders", "Address")
    users = Address.objects.filter(address_type="billing").values_list("user_id", flat=True).distinct()
    for user_id in users:
        source = Address.objects.filter(user_id=user_id, address_type="billing").order_by("-is_default", "updated_at", "id").first()
        if source is None:
            continue
        if not source.is_default:
            source.is_default = True
            source.save(update_fields=["is_default"])
        Address.objects.create(
            user_id=source.user_id,
            address_type="delivery",
            full_name=source.full_name,
            phone=source.phone,
            line1=source.line1,
            line2=source.line2,
            city=source.city,
            district=source.district,
            state=source.state,
            postal_code=source.postal_code,
            country=source.country,
            is_default=True,
        )


class Migration(migrations.Migration):
    dependencies = [("orders", "0003_agent_promo_snapshots")]

    operations = [
        migrations.AddField(
            model_name="address",
            name="address_type",
            field=models.CharField(choices=[("billing", "Billing"), ("delivery", "Delivery")], default="billing", max_length=12),
        ),
        migrations.AddField(
            model_name="order",
            name="billing_address",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="billed_orders", to="orders.address"),
        ),
        migrations.RunPython(copy_legacy_addresses_to_delivery, migrations.RunPython.noop),
    ]
