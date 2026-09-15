from django.db import migrations


def seed_sequences(apps, schema_editor):
    SequenceCounter = apps.get_model("orders", "SequenceCounter")
    for name in ("order", "invoice_b2c", "invoice_b2b"):
        SequenceCounter.objects.get_or_create(name=name, defaults={"next_value": 1})


class Migration(migrations.Migration):
    dependencies = [("orders", "0012_sequencecounter_order_invoice_from_address_and_more")]
    operations = [migrations.RunPython(seed_sequences, migrations.RunPython.noop)]
