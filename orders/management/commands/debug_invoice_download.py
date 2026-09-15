from django.core.management.base import BaseCommand

from orders.models import Invoice


class Command(BaseCommand):
    help = "Test the authenticated invoice PDF download path for an existing invoice."

    def add_arguments(self, parser):
        parser.add_argument("invoice_number")

    def handle(self, *args, **options):
        invoice = Invoice.objects.get(invoice_number=options["invoice_number"])
        self.stdout.write(f"invoice={invoice.invoice_number}")
        self.stdout.write(f"file={invoice.pdf_file.name or '-'}")
        self.stdout.write(f"storage={type(invoice.pdf_file.storage).__module__}.{type(invoice.pdf_file.storage).__name__}")
        if not invoice.pdf_file.name:
            raise RuntimeError("Invoice has no stored PDF reference")
        storage = invoice.pdf_file.storage
        if hasattr(storage, "open_for_download"):
            file_handle = storage.open_for_download(invoice.pdf_file.name)
        else:
            file_handle = storage.open(invoice.pdf_file.name, "rb")
        pdf_bytes = file_handle.read()
        file_handle.close()
        if not pdf_bytes.startswith(b"%PDF"):
            raise RuntimeError("Downloaded invoice file is not a valid PDF")
        self.stdout.write(self.style.SUCCESS(f"DOWNLOAD SUCCESS bytes={len(pdf_bytes)} content_type=application/pdf"))
