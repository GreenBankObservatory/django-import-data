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
        parser.add_argument("--no-progress", action="store_true")
        parser.add_argument("--always-hash", action="store_true")
        parser.add_argument("--quiet", action="store_true")
        parser.add_argument("--all", action="store_true")

    @transaction.atomic
    def handle(self, *args, **kwargs):
        paths = kwargs.get("paths", None)
        quiet = kwargs.get("quiet", False)
        refresh_all = kwargs.get("all", False)
        no_progress = kwargs.get("no_progress", False)

        file_importers = FileImporter.objects.none()
        if refresh_all:
            file_importers = FileImporter.objects.all()
        else:
            paths = paths if paths else []
            if not isatty(sys.stdin.fileno()):
                paths += [line.strip() for line in sys.stdin]

            if paths:
                file_importers = FileImporter.objects.filter(file_path__in=paths)

                if not quiet:
                    paths_not_yet_imported = sorted(
                        set(paths).difference(
                            set(file_importers.values_list("file_path", flat=True))
                        )
                    )

                    if paths_not_yet_imported:
                        print(
                            "The following recently-modified files do not have corresponding "
                            "File Importers:"
                        )
                        print("  " + "\n  ".join(paths_not_yet_imported))

                paths_to_be_refreshed = sorted(
                    set(paths).intersection(
                        set(file_importers.values_list("file_path", flat=True))
                    )
                )

                if paths_to_be_refreshed:
                    print("\nThe following recently-modified files will be refreshed:")
                    print("  " + "\n  ".join(paths_to_be_refreshed))
            else:
                if not quiet:
                    print("No paths given!")

        if not quiet:
            print("\n")
        if file_importers.count():
            print(
                f"Refreshing {file_importers.count()} File Importers "
                f"from the filesystem"
            )
            report = file_importers.refresh_from_filesystem(
                quiet=no_progress, always_hash=kwargs["always_hash"]
            )

            for status, file_importers in report.items():
                if status in ["changed"]:
                    the_paths = "\n".join([fi.file_path for fi in file_importers])
                    print(f"{status}\n{'-' * len(status)}\n{the_paths}\n")
        elif not quiet:
            print("No file importers to refresh!")
