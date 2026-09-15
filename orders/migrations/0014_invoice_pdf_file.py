from django.db import migrations, models

import orders.storage


class Migration(migrations.Migration):
    dependencies = [("orders", "0013_seed_invoice_sequences")]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="pdf_file",
            field=models.FileField(blank=True, null=True, storage=orders.storage.InvoicePDFStorage(), upload_to="invoices/%Y/%m/"),
        ),
    ]
