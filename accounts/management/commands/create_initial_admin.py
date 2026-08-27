import os
from getpass import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from accounts.models import UserProfile


class Command(BaseCommand):
    help = "Create or normalize the initial Phoenix Interior Hub Admin account for development bootstrap."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Initial bootstrap password. It is hashed before storage.")
        parser.add_argument("--email", default="phoenixinteriorhub@gmail.com", help="Admin email address.")

    def handle(self, *args, **options):
        password = options.get("password") or os.environ.get("PHOENIX_INITIAL_ADMIN_PASSWORD")
        if not password and options.get("interactive"):
            password = getpass("Initial Phoenix Interior Hub Admin password: ")
        if not password:
            raise CommandError("Provide --password, set PHOENIX_INITIAL_ADMIN_PASSWORD, or run interactively.")
        user, created = User.objects.get_or_create(
            username="adminabhilash",
            defaults={
                "email": options["email"],
                "first_name": "Abhilash",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password", "email", "first_name", "is_active", "is_staff", "is_superuser"])
            action = "created"
        else:
            changed_fields = []
            if not user.is_active:
                user.is_active = True
                changed_fields.append("is_active")
            if not user.is_staff:
                user.is_staff = True
                changed_fields.append("is_staff")
            if not user.is_superuser:
                user.is_superuser = True
                changed_fields.append("is_superuser")
            if changed_fields:
                user.save(update_fields=changed_fields)
            action = "already exists"

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.role != UserProfile.ADMIN:
            profile.role = UserProfile.ADMIN
            profile.save(update_fields=["role", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"Initial Phoenix Interior Hub Admin account {action}."))
        self.stdout.write("Change the bootstrap password before production use.")
