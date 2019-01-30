"""Provides BaseImportCommand: an abstract class for creating Importers"""

from pprint import pformat
import csv
from enum import Enum
import json
import os
import random
import re

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, F

from tqdm import tqdm


class BaseImportCommand(BaseCommand):
    # output will automatically be wrapped with BEGIN; and COMMIT;
    output_transaction = True
    # prints a warning if the set of migrations on disk don’t match the migrations in the database
    requires_migrations_checks = True

    class PROGRESS_TYPES(Enum):
        ROW = "ROW"
        FILE = "FILE"

    PROGRESS_TYPE = None

    START_INDEX_DEFAULT = 0
    END_INDEX_DEFAULT = None

    @classmethod
    def add_core_arguments(cls, parser):
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
            "-D", "--durable", action="store_true", help="Continue past record errors"
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help=(
                "If a previoius File Import Attempt is detected for one or more "
                "of the given paths, delete and re-create it (overwrite it)"
            ),
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=float,
            help="Specify a random percentage [0.0 - 1.0] of records that should be processed",
        )
        parser.add_argument(
            "--start_index",
            type=int,
            default=cls.START_INDEX_DEFAULT,
            help="Used in conjunction with end_index to determine the slice of records to be processed",
        )
        parser.add_argument(
            "--end_index",
            type=int,
            default=cls.END_INDEX_DEFAULT,
            help="Used in conjunction with start_index to determine the slice of records to be processed",
        )
        if cls.PROGRESS_TYPE == cls.PROGRESS_TYPES.ROW:
            parser.add_argument(
                "-r",
                "--rows",
                nargs="+",
                type=int,
                help="List of specific rows to process (by index)",
            )
        return parser

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+")
        self.add_core_arguments(parser)

    @staticmethod
    def determine_files_to_process(paths, pattern=".*"):
        """Find all files in given paths that match given pattern; sort and return"""

        files = []
        for path in paths:
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                files.extend(
                    [
                        os.path.join(path, file)
                        for file in os.listdir(path)
                        if re.search(pattern, file)
                    ]
                )
            else:
                raise ValueError(f"Given path {path!r} is not a directory or file!")

        return sorted(files)

    @staticmethod
    def load_rows(path):
        """Load rows from a CSV file"""
        with open(path, newline="", encoding="latin1") as file:
            lines = file.readlines()

        return csv.DictReader(lines)

    def handle_record(self, record, file_import_attempt):
        """Provides logic for importing individual records"""

        raise NotImplementedError("Must be implemented by child class")

    def determine_records_to_process(
        self,
        records,
        rows_to_process=None,
        limit=None,
        start_index=START_INDEX_DEFAULT,
        end_index=END_INDEX_DEFAULT,
    ):
        """Return subset of given records

        First, a slice is taken using `start_index` and `end_index`.
        Then, if limit is given, if is used to randomly select a further subset
        of records
        """

        if rows_to_process and limit:
            raise ValueError("Cannot give both rows_to_process and limit!")

        if rows_to_process:
            return [records[index] for index in rows_to_process]

        sliced = records[start_index:end_index]
        num_sliced = len(sliced)

        if limit is not None:
            if limit >= 1:
                return sliced

            # Determine how many records we want to return
            goal = int(num_sliced * limit)
            # Ensure that there is always at least one record returned
            if goal < 1:
                goal = 1

            random_indices = set()
            # Generate unique random indices until we have reached the goal
            while len(random_indices) < goal:
                random_indices.add(random.randint(0, num_sliced - 1))

            sliced = [sliced[index] for index in random_indices]

        return sliced

    def handle_records(self, path, durable=False, overwrite=False, **options):
        rows = list(self.load_rows(path))
        if not rows:
            tqdm.write(f"No rows found in {path}; skipping")
            return None
        FileImporter = apps.get_model("django_import_data.FileImporter")
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        RowData = apps.get_model("django_import_data.RowData")
        # TODO: How to handle changes in path? That is, if a Batch file is moved
        # somewhere else we still need a way to force its association with the
        # existing Batch in the DB. Allow explicit Batch ID to be passed in?
        # Some other unique ID?
        current_command = self.__module__.split(".")[-1]
        file_importer, file_importer_created = FileImporter.objects.get_or_create(
            last_imported_path=path, importer_name=current_command
        )
        previous_file_import_attempt = file_importer.file_import_attempts.order_by(
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
            tqdm.write(f"Deleted {num_deletions} models:\n{pformat(deletions)}")

        file_import_attempt = FileImportAttempt.objects.create(
            file_importer=file_importer, imported_from=path
        )

        if self.PROGRESS_TYPE == self.PROGRESS_TYPES.ROW:
            rows_to_process = options.get("rows", None)
            limit = options.get("limit", None)
            start_index = options.get("start_index", None)
            end_index = options.get("end_index", None)
            rows = self.determine_records_to_process(
                rows,
                rows_to_process=rows_to_process,
                limit=limit,
                start_index=start_index,
                end_index=end_index,
            )

            if rows_to_process:
                tqdm.write(f"Processing only rows {rows_to_process}")

            if limit is not None:
                # if start_index != self.START_INDEX_DEFAULT or end_index != self.END_INDEX_DEFAULT:
                #     slice_str =
                tqdm.write(
                    f"Processing {len(rows)} rows ({limit * 100:.2f}% "
                    "of rows, randomly selected)"
                )
            rows = tqdm(rows, desc=self.help, unit="rows")

        all_errors = []

        for ri, row in enumerate(rows):
            row_data = RowData.objects.create(
                row_num=ri, data=row, file_import_attempt=file_import_attempt
            )
            self.handle_record(row_data, file_import_attempt)
            errors = {
                import_attempt.imported_by: import_attempt.errors
                for import_attempt in row_data.model_import_attempts.all()
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
        file_import_attempt.errors.update(errors)
        file_import_attempt.save()
        return file_import_attempt

        # raise ValueError("hmmm")

    def summary(self, file_import_attempt, all_errors):
        error_summary = {}
        total_form_errors = 0
        total_conversion_errors = 0
        creations = (
            file_import_attempt.rows.filter(
                model_import_attempts__status__startswith="created"
            )
            .values(model=F("model_import_attempts__content_type__model"))
            .annotate(creation_count=Count("model_import_attempts__status"))
        )

        for row_errors in all_errors:
            for attribute, attribute_errors in row_errors.items():
                error_summary.setdefault(attribute, {})
                conversion_errors = attribute_errors.get("conversion_errors", {})
                total_conversion_errors += len(conversion_errors)
                for conversion_error in conversion_errors:
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

                form_errors = attribute_errors.get("form_errors", {})
                total_form_errors += len(form_errors)
                for form_error in form_errors:
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
            tqdm.write("Created {creation_count} {model} objects".format(**creation))
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
        files_to_process = self.determine_files_to_process(options["paths"])

        print(f"PROGRESS_TYPE: {self.PROGRESS_TYPE}")
        if self.PROGRESS_TYPE == self.PROGRESS_TYPES.FILE:
            files_to_process = self.determine_records_to_process(
                files_to_process, limit=options.get("limit", None)
            )
            files_to_process = tqdm(files_to_process, desc=self.help, unit="files")
        for path in files_to_process:
            tqdm.write(f"Processing {path}")
            self.handle_records(path, **options)

        if options["dry_run"]:
            transaction.set_rollback(True)
            tqdm.write("DRY RUN; rolling back changes")
