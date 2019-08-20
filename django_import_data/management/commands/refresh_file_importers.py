from os import isatty
import sys

from django.core.management.base import BaseCommand
from django.utils.timezone import datetime

from django.db import transaction

from django_import_data.models import FileImporter


def parse_date(date_str):
    return datetime.strptime(date_str, r"%m/%d/%Y %H:%M:%S%z")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--paths", nargs="+")
        parser.add_argument("--since", type=parse_date)
        parser.add_argument("--no-progress", action="store_true")
        parser.add_argument("--always-hash", action="store_true")

    @transaction.atomic
    def handle(self, *args, **kwargs):
        since = kwargs.get("since", None)
        paths = kwargs.get("paths", None)
        quiet = kwargs.get("quiet", False)
        no_progress = kwargs.get("no_progress", False)
        file_importers = FileImporter.objects.all()
        since_str = ""

        paths = paths if paths else []
        if not isatty(sys.stdin.fileno()):
            paths += [line.strip() for line in sys.stdin]

        if since:
            file_importers |= FileImporter.objects.filter(file_modified_on__gte=since)
            since_str = f" (i.e. those modified since {str(since)})"

        if paths:
            file_importers &= FileImporter.objects.filter(file_path__in=paths)

        if not quiet:
            print(
                "The following recently-modified files do not have corresponding File Importers:"
            )
            print(
                "\n  "
                + "\n  ".join(
                    sorted(
                        set(paths).difference(
                            set(file_importers.values_list("file_path", flat=True))
                        )
                    )
                )
            )
            print("\nThe following recently-modified files will be refreshed:")
            print(
                "\n  "
                + "\n  ".join(
                    sorted(
                        set(paths).intersection(
                            set(file_importers.values_list("file_path", flat=True))
                        )
                    )
                )
            )
            print(
                f"Refreshing {file_importers.count()} File Importers "
                f"from the filesystem{since_str}"
            )
        if file_importers.count():
            report = file_importers.refresh_from_filesystem(
                quiet=no_progress, always_hash=kwargs["always_hash"]
            )

            for status, file_importers in report.items():
                if status in ["changed"]:
                    the_paths = "\n".join([fi.file_path for fi in file_importers])
                    print(f"{status}\n{'-' * len(status)}\n{the_paths}\n")
