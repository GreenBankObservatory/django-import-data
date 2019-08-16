from django.core.management.base import BaseCommand

from django_import_data.models import FileImporter
from django.utils.timezone import datetime


def parse_date(date_str):
    return datetime.strptime(date_str, r"%m/%d/%Y %H:%M:%S%z")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--since", type=parse_date)

    def handle(self, *args, **kwargs):
        since = kwargs.get("since", None)
        if since:
            file_importers = FileImporter.objects.filter(file_modified_on__gte=since)
            since_str = f" (i.e. those modified since {str(since)})"
        else:
            file_importers = FileImporter.objects.all()
            since_str = ""

        if file_importers.count():
            print(
                f"Refreshing {file_importers.count()} File Importers from the filesystem{since_str}"
            )
            file_importers.refresh_from_filesystem()
