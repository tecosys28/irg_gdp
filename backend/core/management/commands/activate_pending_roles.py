"""
One-time command: activate all PENDING roles for users who have a firebase_uid
(i.e. users who registered via Firebase authentication).

Run once on EC2 after deployment:
  python manage.py activate_pending_roles
  python manage.py activate_pending_roles --dry-run
"""
from django.core.management.base import BaseCommand
from core.models import UserRole


class Command(BaseCommand):
    help = 'Activate PENDING roles for Firebase-authenticated users'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    def handle(self, *args, **options):
        dry = options['dry_run']
        qs = UserRole.objects.filter(status='PENDING', user__firebase_uid__isnull=False)
        count = qs.count()
        self.stdout.write(f'Found {count} PENDING role(s) for Firebase users.')
        if not dry:
            qs.update(status='ACTIVE')
            self.stdout.write(self.style.SUCCESS(f'Activated {count} role(s).'))
        else:
            for r in qs.select_related('user'):
                self.stdout.write(f'  [DRY] {r.user.email} → {r.role}')
            self.stdout.write('Dry run complete — no changes saved.')
