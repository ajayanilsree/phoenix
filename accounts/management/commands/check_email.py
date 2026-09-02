from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check email configuration without displaying credentials."

    def handle(self, *args, **options):
        checks = {
            "Email backend configured": bool(settings.EMAIL_BACKEND),
            "SMTP host configured": bool(settings.EMAIL_HOST),
            "SMTP login configured": bool(settings.EMAIL_HOST_USER),
            "SMTP password configured": bool(settings.EMAIL_HOST_PASSWORD),
            "Default sender configured": bool(settings.DEFAULT_FROM_EMAIL),
        }
        for label, configured in checks.items():
            self.stdout.write(f"{label}: {'YES' if configured else 'NO'}")
        self.stdout.write(f"Email configuration: {'READY' if all(checks.values()) else 'NOT READY'}")
