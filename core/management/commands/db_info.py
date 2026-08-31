from .database_health import Command as DatabaseHealthCommand


class Command(DatabaseHealthCommand):
    help = "Show safe database configuration and record counts without printing credentials."
