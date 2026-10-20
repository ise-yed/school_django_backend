from django.core.management.commands.migrate import Command as MigrateCommand

class Command(MigrateCommand):
    def sync_apps(self, connection, app_labels):
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        return super().sync_apps(connection, app_labels)

# جایگزینی دستور migrate
import django.core.management.commands.migrate
django.core.management.commands.migrate.Command = Command