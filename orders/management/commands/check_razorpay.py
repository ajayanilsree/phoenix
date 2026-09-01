from django.core.management.base import BaseCommand
from django.conf import settings

from orders.payment import razorpay_is_configured, razorpay_sdk_available


class Command(BaseCommand):
    help = "Check whether Razorpay is configured without displaying credentials."

    def handle(self, *args, **options):
        key_id_configured = bool(settings.RAZORPAY_KEY_ID)
        key_secret_configured = bool(settings.RAZORPAY_KEY_SECRET)
        self.stdout.write(f"Razorpay Key ID configured: {'YES' if key_id_configured else 'NO'}")
        self.stdout.write(f"Razorpay Key Secret configured: {'YES' if key_secret_configured else 'NO'}")
        sdk_ready = razorpay_sdk_available()
        self.stdout.write(f"Razorpay SDK import: {'OK' if sdk_ready else 'MISSING'}")
        self.stdout.write(
            f"Razorpay configuration: {'READY' if razorpay_is_configured() and sdk_ready else 'NOT READY'}"
        )
