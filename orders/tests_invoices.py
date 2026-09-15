from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from catalog.models import Category, Product
from .invoices import InvoiceGenerationError, generate_invoice, invoice_company_details, next_sequence
from .models import Address, Invoice, Order, OrderItem


class InvoiceGenerationTests(TestCase):
    def setUp(self):
        self.pdf_directory = TemporaryDirectory()
        self.addCleanup(self.pdf_directory.cleanup)
        self.invoice_pdf_field = Invoice._meta.get_field("pdf_file")
        self.original_pdf_storage = self.invoice_pdf_field.storage
        self.invoice_pdf_field.storage = FileSystemStorage(location=self.pdf_directory.name)
        self.addCleanup(self._restore_invoice_storage)
        User = get_user_model()
        self.customer = User.objects.create_user(username="invoice-customer", password="test-password", first_name="Asha")
        self.customer.profile.role = UserProfile.CUSTOMER
        self.customer.profile.save(update_fields=["role"])
        self.staff = User.objects.create_user(username="invoice-staff", password="test-password")
        self.staff.profile.role = UserProfile.STAFF
        self.staff.profile.save(update_fields=["role"])
        self.admin = User.objects.create_superuser(username="invoice-admin", password="test-password", email="admin@example.com")
        category = Category.objects.create(name="Invoice Category", slug="invoice-category")
        product = Product.objects.create(name="GST Board", slug="gst-board", sku="GST-001", category=category, price=Decimal("118.00"), gst_rate=18)
        address_data = {"user": self.customer, "address_type": Address.DELIVERY, "full_name": "Asha Customer", "phone": "9999999999", "line1": "Main Road", "city": "Kochi", "district": "Ernakulam", "state": "Kerala", "postal_code": "682001"}
        self.address = Address.objects.create(**address_data)
        self.order = Order.objects.create(order_number="PHXS000001", customer=self.customer, shipping_address=self.address, billing_address=self.address, payment_status="paid", status=Order.CONFIRMED, grand_total=Decimal("118.00"))
        OrderItem.objects.create(order=self.order, product=product, product_name=product.name, sku=product.sku, hsn_code="4411", gst_rate_snapshot=18, unit_type="piece", unit_price=Decimal("118.00"), quantity=1, line_total=Decimal("118.00"))

    def _restore_invoice_storage(self):
        self.invoice_pdf_field.storage = self.original_pdf_storage

    def test_invoice_is_b2c_and_idempotent(self):
        invoice = generate_invoice(self.order, self.staff, "Phoenix Warehouse\nKochi")
        self.assertEqual(invoice.invoice_number, "PHXINTB2C000001")
        self.assertEqual(invoice.invoice_type, Invoice.B2C)
        self.assertEqual(invoice.cgst_total, Decimal("9.00"))
        self.assertEqual(invoice.sgst_total, Decimal("9.00"))
        self.assertEqual(self.order.refresh_from_db(), None)
        self.assertEqual(self.order.status, Order.PACKED)
        self.assertEqual(generate_invoice(self.order, self.staff, "ignored").pk, invoice.pk)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.igst_total, Decimal("0.00"))
        self.assertEqual(invoice_company_details()["company_gstin"], "32AGSPA6127E1ZQ")

    def test_agent_order_uses_b2b_series(self):
        self.customer.profile.role = UserProfile.AGENT
        self.customer.profile.save(update_fields=["role"])
        invoice = generate_invoice(self.order, self.staff, "Phoenix Warehouse")
        self.assertEqual(invoice.invoice_number, "PHXINTB2B000001")
        self.assertEqual(invoice.invoice_type, Invoice.B2B)

    def test_missing_sequence_counter_is_recreated(self):
        from .models import SequenceCounter

        SequenceCounter.objects.filter(name="invoice_b2c").delete()
        invoice = generate_invoice(self.order, self.staff, "Phoenix Warehouse")
        self.assertEqual(invoice.invoice_number, "PHXINTB2C000001")

    def test_invoice_sequence_recovers_from_existing_invoice(self):
        Invoice.objects.create(
            order=self.order,
            invoice_number="PHXINTB2C000007",
            invoice_type=Invoice.B2C,
            invoice_date=self.order.created_at,
            company_name="Phoenix Interior Hub",
            from_address="Phoenix Warehouse",
            grand_total=self.order.grand_total,
        )
        from .models import SequenceCounter

        SequenceCounter.objects.filter(name="invoice_b2c").delete()
        self.assertEqual(next_sequence("invoice_b2c"), 8)

    def test_legacy_item_snapshots_fall_back_to_product_data(self):
        item = self.order.items.first()
        item.product_name = ""
        item.hsn_code = ""
        item.gst_rate_snapshot = 0
        item.unit_type = ""
        item.save(update_fields=["product_name", "hsn_code", "gst_rate_snapshot", "unit_type"])
        invoice = generate_invoice(self.order, self.staff, "Phoenix Warehouse")
        invoice_item = invoice.items.get()
        self.assertEqual(invoice_item.description, "GST Board")
        self.assertEqual(invoice_item.hsn_code, "")
        self.assertEqual(invoice_item.unit, "NOS")
        self.assertEqual(invoice_item.gst_rate, Decimal("18.00"))

    def test_admin_can_submit_packed_status_and_generate_invoice(self):
        self.client.login(username="invoice-admin", password="test-password")
        response = self.client.post(
            reverse("admin_order_detail", args=[self.order.order_number]),
            {"status": Order.PACKED, "invoice_from_address": "Phoenix Warehouse"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Invoice.objects.filter(order=self.order).exists())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.PACKED)

    def test_unpaid_order_cannot_generate_invoice(self):
        self.order.payment_status = "pending"
        self.order.save(update_fields=["payment_status"])
        with self.assertRaises(InvoiceGenerationError):
            generate_invoice(self.order, self.staff, "Phoenix Warehouse")
        self.assertFalse(Invoice.objects.exists())

    def test_pdf_download_renders(self):
        invoice = generate_invoice(self.order, self.staff, "Phoenix Warehouse")
        self.client.login(username="invoice-admin", password="test-password")
        list_response = self.client.get(reverse("admin_invoices"))
        self.assertEqual(list_response.status_code, 200)
        self.assertNotContains(list_response, ">View<")
        self.assertContains(list_response, "Download PDF")
        response = self.client.get(reverse("admin_invoice_pdf", args=[invoice.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
