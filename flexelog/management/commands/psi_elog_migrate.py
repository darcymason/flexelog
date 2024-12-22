from django.core.management.base import BaseCommand, CommandError
from flexelog.models import Logbook


class Command(BaseCommand):
    help = "Migrate a file-based PSI elog to Flexelog"

    def add_arguments(self, parser):
        parser.add_argument("--logbooks", nargs="*", type=str)

    def handle(self, *args, **options):
        for lb_name in options["logbooks"]:  # XXX or do all if none specified
            self.stdout.write(f"Migrating PSI logbook '{lb_name}'", ending="...")
            # XXX do the work
            self.stdout.write(self.style.SUCCESS("OK"))
            # ... raise CommandError('XXX')


        self.stdout.write(
            self.style.SUCCESS("Successfully migrated PSI logbooks")  # XX specify
        )