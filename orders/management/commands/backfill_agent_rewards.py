from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from orders.rewards import reconcile_agent_rewards


class Command(BaseCommand):
    help = "Backfill idempotent agent reward ledger entries for eligible paid orders."

    def handle(self, *args, **options):
        User = get_user_model()
        total = 0
        for agent in User.objects.filter(profile__role=UserProfile.AGENT).iterator():
            created = reconcile_agent_rewards(agent)
            total += created
            self.stdout.write(f"{agent.username}: {created} reward entries created")
        self.stdout.write(self.style.SUCCESS(f"Completed. {total} reward entries created."))
