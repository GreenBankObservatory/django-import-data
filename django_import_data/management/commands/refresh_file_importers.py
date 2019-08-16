from django.core.management.base import BaseCommand

from django_import_data.models import FileImporter


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        print(
            f"Refreshing {FileImporter.objects.count()} File Importers from the filesystem"
        )
        FileImporter.objects.all().refresh_from_filesystem()
