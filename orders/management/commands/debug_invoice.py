from django.core.management.base import BaseCommand

from orders.invoices import generate_invoice
from orders.models import Invoice, Order


class Command(BaseCommand):
    help = "Print production invoice data and run the normal invoice-generation service."

    def add_arguments(self, parser):
        parser.add_argument("order_number")
        parser.add_argument("--from-address", default="Render debug invoice address")

    def handle(self, *args, **options):
        order = (
            Order.objects.select_related("customer", "billing_address", "shipping_address")
            .prefetch_related("items__product", "items__variant")
            .get(order_number=options["order_number"])
        )
        invoice = Invoice.objects.filter(order=order).first()
        self.stdout.write(f"ORDER: {order.order_number}")
        self.stdout.write(f"payment_status={order.payment_status} status={order.status} total={order.grand_total}")
        self.stdout.write(f"customer={order.customer.username if order.customer else '-'}")
        self.stdout.write(f"billing_address={order.billing_address or '-'}")
        self.stdout.write(f"shipping_address={order.shipping_address or '-'}")
        self.stdout.write(f"invoice_from_address={order.invoice_from_address or '-'}")
        self.stdout.write(f"invoice_exists={bool(invoice)} invoice_number={invoice.invoice_number if invoice else '-'} pdf={invoice.pdf_file.name if invoice and invoice.pdf_file.name else '-'}")
        for item in order.items.all():
            source = item.variant or item.product
            self.stdout.write(
                "ITEM "
                f"product={item.product_id} variant={item.variant_id} "
                f"name={item.product_name or '-'} selected_variant={item.selected_variant or '-'} "
                f"hsn={item.hsn_code or '-'} gst={item.gst_rate_snapshot} unit={item.unit_type or '-'} "
                f"quantity={item.quantity} unit_price={item.unit_price} line_total={item.line_total} "
                f"pricing_type={item.pricing_type} source={source or '-'}"
            )
        self.stdout.write(f"from_address_used={options['from_address']}")
        # Deliberately do not catch exceptions: Render Shell must show the full traceback.
        result = generate_invoice(order, generated_by=None, from_address=options["from_address"])
        order.refresh_from_db(fields=["status"])
        self.stdout.write(self.style.SUCCESS(f"SUCCESS invoice={result.invoice_number} pdf={result.pdf_file.name or '-'} status={order.status}"))
