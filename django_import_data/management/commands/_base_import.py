import csv

# from pprint import pformat
import json
import random

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction

from django.apps import apps


class BaseImportCommand(BaseCommand):
    # output will automatically be wrapped with BEGIN; and COMMIT;
    output_transaction = True
    # prints a warning if the set of migrations on disk don’t match the migrations in the database
    requires_migrations_checks = True

    @staticmethod
    def add_core_arguments(parser):
        """Add the set of args that are common across all import commands"""
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help=(
                "Roll back all database changes after execution. Note that "
                "this will leave gaps in the PKs where created objects were rolled back"
            ),
        )
        parser.add_argument(
            "-D", "--durable", action="store_true", help="Continue past row errors"
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=float,
            help="Specify a random percentage [0.0 - 1.0] of rows that should be processed",
        )
        return parser

    def add_arguments(self, parser):
        # TODO: Allow multiple paths for all importers
        parser.add_argument("path")
        self.add_core_arguments(parser)

    def load_rows(self, path):
        """Load rows from a CSV file"""
        with open(path, newline="", encoding="latin1") as file:
            lines = file.readlines()

        return csv.DictReader(lines)

    @transaction.atomic
    def handle_row(self, row):
        raise NotImplementedError("Must be implemented by child class")

    def get_random_rows(self, rows, limit):
        if limit >= 1:
            return rows
        num_rows = len(rows)
        goal = int(num_rows * limit)

        random_indices = set()
        while len(random_indices) < goal:
            random_indices.add(random.randint(0, num_rows - 1))

        return [rows[index] for index in random_indices]

    def handle_rows(self, path, durable=False, **options):
        FileImporter = apps.get_model("django_import_data.FileImporter")
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        # TODO: How to handle changes in path? That is, if a Batch file is moved
        # somewhere else we still need a way to force its association with the
        # existing Batch in the DB. Allow explicit Batch ID to be passed in?
        # Some other unique ID?
        file_importer, file_importer_created = FileImporter.objects.get_or_create(
            last_imported_path=path
        )
        file_import_attempt = FileImportAttempt.objects.create(
            file_importer=file_importer, imported_from=path
        )
        rows = list(self.load_rows(path))
        limit = options.get("limit", None)
        if limit is not None:
            rows = self.get_random_rows(rows, limit)

        for row in tqdm(rows, desc=self.help, unit="rows"):
            try:
                audits = self.handle_row(row, file_import_attempt)
            except ValueError as error:
                tqdm.write(f"Failed to handle row (conversion errors): {row}")
                if not durable:
                    raise error
                tqdm.write(f"  Error: {error!r}")
            else:
                # if not isinstance(audits, dict) is None:
                #     raise ValueError("handle_row must return audit info as a dict!")
                errors = {
                    formmap_name: audit.errors
                    for formmap_name, audit in audits.items()
                    if audit
                }
                if errors:
                    error_str = (
                        f"Row handled, but had {len(errors)} errors:\n"
                        f"{json.dumps(errors, indent=2)}"
                    )
                    if durable:
                        tqdm.write(error_str)
                    else:
                        raise ValueError(error_str)

    @transaction.atomic
    def handle(self, *args, **options):
        self.handle_rows(*args, **options)
        if options["dry_run"]:
            transaction.set_rollback = True
            print("DRY RUN; rolling back changes")
