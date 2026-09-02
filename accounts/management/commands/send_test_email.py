import logging

from django.core.management.base import BaseCommand, CommandError

from accounts.services.email_service import send_test_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send a test email using Django's configured email backend."

    def add_arguments(self, parser):
        parser.add_argument("recipient")

    def handle(self, *args, **options):
        try:
            sent = send_test_email(options["recipient"])
        except Exception:
            logger.exception("Configured email test delivery failed.")
            raise CommandError("Email sending failed. Check server logs for details.") from None
        if not sent:
            raise CommandError("Email backend did not report a sent message.")
        self.stdout.write(self.style.SUCCESS("Email sent successfully."))
