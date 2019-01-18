import csv
import json
from pprint import pformat
import random

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q, F
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
            "--overwrite",
            action="store_true",
            help=(
                # TODO: NEEDS WORK
                "Overwrite previous FIA"
            ),
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=float,
            help="Specify a random percentage [0.0 - 1.0] of rows that should be processed",
        )
        parser.add_argument(
            "-r",
            "--rows",
            nargs="+",
            type=int,
            help="List of specific rows to process (by index)",
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
        if goal < 1:
            goal = 1

        random_indices = set()
        while len(random_indices) < goal:
            random_indices.add(random.randint(0, num_rows - 1))

        return [rows[index] for index in random_indices]

    def handle_rows(self, path, durable=False, overwrite=False, **options):
        FileImporter = apps.get_model("django_import_data.FileImporter")
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        # TODO: How to handle changes in path? That is, if a Batch file is moved
        # somewhere else we still need a way to force its association with the
        # existing Batch in the DB. Allow explicit Batch ID to be passed in?
        # Some other unique ID?
        if FileImporter.objects.filter(last_imported_path=path).exists():
            file_importer = FileImporter.objects.get(last_imported_path=path)
        file_importer, file_importer_created = FileImporter.objects.get_or_create(
            last_imported_path=path
        )
        previous_file_import_attempt = file_importer.import_attempts.order_by(
            "created_on"
        ).last()
        if previous_file_import_attempt:
            tqdm.write(
                f"Previous FIA found; deleting it: {previous_file_import_attempt}"
            )
            if not overwrite:
                raise ValueError(
                    f"Found previous File Import Attempt '{previous_file_import_attempt}', "
                    "but cannot delete it due to presence of overwrite=False!"
                )
            num_deletions, deletions = (
                previous_file_import_attempt.delete_imported_models()
            )
            print(f"Deleted {num_deletions} models:\n{pformat(deletions)}")
        file_import_attempt = FileImportAttempt.objects.create(
            file_importer=file_importer, imported_from=path
        )
        rows = list(self.load_rows(path))
        rows_to_process = options.get("rows", None)
        if rows_to_process:
            rows = [rows[ri] for ri in rows_to_process]
            tqdm.write(f"Processing only rows {rows_to_process}")

        limit = options.get("limit", None)
        if limit is not None:
            rows = self.get_random_rows(rows, limit)
            tqdm.write(
                f"Processing {len(rows)} rows ({limit * 100:.2f}% "
                "of rows, randomly selected)"
            )

        all_errors = []

        for ri, row in enumerate(tqdm(rows, desc=self.help, unit="rows")):
            row_data = self.handle_row(row, file_import_attempt)
            errors = {
                import_attempt.imported_by: import_attempt.errors
                for import_attempt in row_data.import_attempts.all()
                if import_attempt.errors
            }
            # TODO: Make status an int in the DB so we can do calcs easier
            if errors:
                error_str = (
                    f"Row {ri} handled, but had {len(errors)} errors:\n"
                    f"{json.dumps(errors, indent=2)}"
                )
                if durable:
                    tqdm.write(error_str)
                else:
                    raise ValueError(error_str)

                all_errors.append(errors)

        creations, errors = self.summary(file_import_attempt, all_errors)
        file_import_attempt.creations = creations
        file_import_attempt.errors = errors
        file_import_attempt.save()

    def summary(self, file_import_attempt, all_errors):
        error_summary = {}
        total_form_errors = 0
        total_conversion_errors = 0
        creations = (
            file_import_attempt.rows.filter(
                import_attempts__status__startswith="created"
            )
            .values(model=F("import_attempts__content_type__model"))
            .annotate(creation_count=Count("import_attempts__status"))
        )

        for row_errors in all_errors:
            for attribute, attribute_errors in row_errors.items():
                error_summary.setdefault(attribute, {})
                total_conversion_errors += len(attribute_errors["conversion_errors"])
                for conversion_error in attribute_errors["conversion_errors"]:
                    error_summary[attribute].setdefault("conversion_errors", {})
                    error_summary[attribute]["conversion_errors"].setdefault("count", 0)
                    error_summary[attribute]["conversion_errors"]["count"] += len(
                        conversion_error
                    )

                    error_summary[attribute]["conversion_errors"].setdefault(
                        "fields", []
                    )
                    if (
                        conversion_error["from_fields"]
                        not in error_summary[attribute]["conversion_errors"]["fields"]
                    ):
                        error_summary[attribute]["conversion_errors"]["fields"].append(
                            conversion_error["from_fields"]
                        )

                total_form_errors += len(attribute_errors["form_errors"])
                for form_error in attribute_errors["form_errors"]:
                    error_summary[attribute].setdefault("form_errors", {})
                    error_summary[attribute]["form_errors"].setdefault("count", 0)
                    error_summary[attribute]["form_errors"]["count"] += len(form_error)

                    error_summary[attribute]["form_errors"].setdefault("fields", [])
                    if (
                        form_error["field"]
                        not in error_summary[attribute]["form_errors"]["fields"]
                    ):
                        error_summary[attribute]["form_errors"]["fields"].append(
                            form_error["field"]
                        )
        tqdm.write("=" * 80)
        tqdm.write("Model Import Summary:")
        for creation in creations:
            print("Created {creation_count} {model} objects".format(**creation))
        tqdm.write("-" * 80)
        tqdm.write("Error Summary:")
        tqdm.write(pformat(error_summary))
        tqdm.write(
            f"  Encountered {total_form_errors + total_conversion_errors} total errors "
            f"across {len(error_summary)} attribute(s):"
        )
        tqdm.write("=" * 80)
        for attribute, attribute_errors in error_summary.items():
            tqdm.write(f"    {attribute} had {len(attribute_errors)} type(s) of error:")
            for error_type, errors_of_type in attribute_errors.items():
                tqdm.write(f"      {error_type}:")
                tqdm.write(
                    f"        {errors_of_type['count']} errors across fields: {errors_of_type['fields']}"
                )

        return [dict(creation) for creation in creations], error_summary

    @transaction.atomic
    def handle(self, *args, **options):
        self.handle_rows(*args, **options)
        if options["dry_run"]:
            transaction.set_rollback = True
            tqdm.write("DRY RUN; rolling back changes")
