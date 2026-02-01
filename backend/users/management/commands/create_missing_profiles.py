# users/management/commands/create_missing_profiles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile


class Command(BaseCommand):
    help = 'Create UserProfile for users that are missing profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--default-role',
            type=str,
            default='beneficiary',
            help='Default role for users without profiles (beneficiary/provider)'
        )
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Automatically create profiles without confirmation'
        )

    def handle(self, *args, **options):
        default_role = options['default_role']
        auto_confirm = options['auto']
        
        if default_role not in ['beneficiary', 'provider']:
            self.stdout.write(
                self.style.ERROR('Invalid role. Must be "beneficiary" or "provider"')
            )
            return

        # Find users without profiles
        users_without_profiles = []
        for user in User.objects.all():
            try:
                _ = user.profile
            except UserProfile.DoesNotExist:
                users_without_profiles.append(user)

        if not users_without_profiles:
            self.stdout.write(
                self.style.SUCCESS('✓ All users already have profiles!')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'Found {len(users_without_profiles)} user(s) without profiles:'
            )
        )

        for user in users_without_profiles:
            self.stdout.write(f'  - {user.username} ({user.email})')

        # Ask for confirmation unless --auto flag is used
        if not auto_confirm:
            confirm = input('\nCreate profiles for these users? (yes/no): ')
            if confirm.lower() not in ['yes', 'y']:
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

        # Create profiles
        created_count = 0
        for user in users_without_profiles:
            # Generate unique phone number placeholder
            phone = f'+91{9000000000 + user.id}'
            
            UserProfile.objects.create(
                user=user,
                phone_number=phone,
                role=default_role,
                is_phone_verified=False
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Created profile for {user.username} (phone: {phone}, role: {default_role})'
                )
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully created {created_count} profile(s)!'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                '\n⚠ Note: Placeholder phone numbers were assigned. '
                'Users should update their phone numbers and verify them.'
            )
        )