from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check email configuration without displaying credentials."

    def handle(self, *args, **options):
        backend_names = {
            "django.core.mail.backends.smtp.EmailBackend": "SMTP",
            "django.core.mail.backends.console.EmailBackend": "Console",
        }
        backend = backend_names.get(settings.EMAIL_BACKEND, settings.EMAIL_BACKEND)
        self.stdout.write(f"Email backend: {backend or 'Unknown'}")
        self.stdout.write(f"SMTP host configured: {'YES' if settings.EMAIL_HOST else 'NO'}")
        self.stdout.write(f"SMTP port: {settings.EMAIL_PORT}")
        self.stdout.write(f"SMTP user configured: {'YES' if settings.EMAIL_HOST_USER else 'NO'}")
        self.stdout.write(f"SMTP password configured: {'YES' if settings.EMAIL_HOST_PASSWORD else 'NO'}")
        self.stdout.write(f"Default sender configured: {'YES' if settings.DEFAULT_FROM_EMAIL else 'NO'}")
        checks = {
            "Email backend configured": settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend",
            "SMTP host configured": bool(settings.EMAIL_HOST),
            "SMTP user configured": bool(settings.EMAIL_HOST_USER),
            "SMTP password configured": bool(settings.EMAIL_HOST_PASSWORD),
            "Default sender configured": bool(settings.DEFAULT_FROM_EMAIL),
        }
        self.stdout.write(f"Email configuration: {'READY' if all(checks.values()) else 'NOT READY'}")
