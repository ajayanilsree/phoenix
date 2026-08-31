from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from catalog.models import Category, Product
from orders.models import Order


class Command(BaseCommand):
    help = "Show safe database configuration and record counts without printing credentials."

    def handle(self, *args, **options):
        database = connection.settings_dict
        backend = connection.vendor
        backend_label = {
            "postgresql": "PostgreSQL",
            "sqlite": "SQLite",
            "mysql": "MySQL",
        }.get(backend, backend or "Unknown")

        self.stdout.write(f"Database backend: {backend_label}")
        self.stdout.write(f"Database host configured: {'YES' if database.get('HOST') or backend == 'sqlite' else 'NO'}")
        self.stdout.write(f"Database name configured: {'YES' if database.get('NAME') else 'NO'}")
        self.stdout.write(f"SQLite: {'YES' if backend == 'sqlite' else 'NO'}")

        try:
            connection.ensure_connection()
            counts = [
                ("Users", get_user_model().objects.count()),
                ("Products", Product.objects.count()),
                ("Orders", Order.objects.count()),
                ("Categories", Category.objects.count()),
            ]
        except Exception as exc:
            raise CommandError(f"Database connection failed: {exc.__class__.__name__}") from exc

        self.stdout.write(self.style.SUCCESS("Connection: OK"))
        for label, count in counts:
            self.stdout.write(f"{label}: {count}")
