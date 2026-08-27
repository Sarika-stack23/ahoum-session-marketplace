"""
Management command to promote a user to Creator role.

Usage:
    python manage.py promote_to_creator <username_or_email>

This is the controlled mechanism for Creator assignment.
The assignment does not specify public self-service role promotion,
so we use an admin-controlled approach that is demo-safe.

See DECISIONS.md for full rationale.
"""
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User


class Command(BaseCommand):
    help = "Promote a user to the Creator role"

    def add_arguments(self, parser):
        parser.add_argument(
            "identifier",
            type=str,
            help="Username or email of the user to promote",
        )

    def handle(self, *args, **options):
        identifier = options["identifier"]

        try:
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                raise CommandError(f'User "{identifier}" not found.')

        if user.role == User.Role.CREATOR:
            self.stdout.write(
                self.style.WARNING(f'User "{user.username}" is already a Creator.')
            )
            return

        user.role = User.Role.CREATOR
        user.save(update_fields=["role"])
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully promoted "{user.username}" ({user.email}) to Creator.'
            )
        )
