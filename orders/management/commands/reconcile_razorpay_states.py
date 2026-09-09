from django.core.management.base import BaseCommand

from orders.models import Order


class Command(BaseCommand):
    help = "Normalize legacy Razorpay orders that were confirmed without verified payment."

    def handle(self, *args, **options):
        invalid_statuses = [
            Order.CONFIRMED,
            Order.PROCESSING,
            Order.PACKED,
            Order.SHIPPED,
            Order.DELIVERED,
        ]
        repaired = Order.objects.filter(
            payment_method="razorpay",
            status__in=invalid_statuses,
        ).exclude(payment_status="paid").update(status=Order.PENDING)
        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} unverified Razorpay order(s)."))
