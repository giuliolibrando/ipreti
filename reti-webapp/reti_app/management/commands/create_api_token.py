from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Create an API token for the data collector'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='datacollector',
            help='Username for the API token (default: datacollector)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='datacollector@uniroma1.it',
            help='Email for the API user (default: datacollector@uniroma1.it)'
        )
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Recreate token if user already exists'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        recreate = options['recreate']

        # Create or get user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,  # Grant staff permissions for API access
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created user: {username}')
            )
        elif recreate:
            # Delete existing token if recreating
            Token.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.WARNING(f'Recreating token for existing user: {username}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'User {username} already exists')
            )

        # Create or get token
        token, token_created = Token.objects.get_or_create(user=user)

        if token_created or recreate:
            self.stdout.write(
                self.style.SUCCESS(f'Token created: {token.key}')
            )
            self.stdout.write(
                self.style.SUCCESS('Add this token to your docker-compose.yml:')
            )
            self.stdout.write(
                self.style.SUCCESS(f'- DJANGO_API_TOKEN={token.key}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Existing token: {token.key}')
            )
            self.stdout.write(
                self.style.SUCCESS('Add this token to your docker-compose.yml:')
            )
            self.stdout.write(
                self.style.SUCCESS(f'- DJANGO_API_TOKEN={token.key}')
            ) 