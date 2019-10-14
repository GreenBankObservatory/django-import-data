"""Provides BaseImportCommand: an abstract class for creating Importers"""

from collections import defaultdict
from datetime import datetime
from enum import Enum
from pprint import pformat
import csv
import json
import logging
import os
import random
import re

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from tqdm import tqdm

from django_import_data.utils import hash_file, determine_files_to_process

LOGGER = logging.getLogger(__name__)


class BaseImportCommand(BaseCommand):
    # output will automatically be wrapped with BEGIN; and COMMIT;
    # output_transaction = True
    # prints a warning if the set of migrations on disk don’t match the migrations in the database
    requires_migrations_checks = True

    class PROGRESS_TYPES(Enum):
        ROW = "ROW"
        FILE = "FILE"

    PROGRESS_TYPE = None

    START_INDEX_DEFAULT = 0
    END_INDEX_DEFAULT = None

    # TODO: This is somewhat stupid; think of a better way
    FORM_MAPS = NotImplemented

    IGNORED_HEADERS = []

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

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--overwrite",
            action="store_true",
            help=(
                "If a previous File Import Attempt is detected for one or more "
                "of the given paths, delete and re-create it (overwrite it)"
            ),
        )
        group.add_argument(
            "--skip",
            action="store_true",
            help=(
                "If a previous File Import Attempt is detected for one or more "
                "of the given paths, skip it"
            ),
        )

        parser.add_argument(
            "-l",
            "--limit",
            type=float,
            help="Specify a random percentage [0.0 - 1.0] of records that should be processed",
        )
        parser.add_argument(
            "--start-index",
            type=int,
            default=cls.START_INDEX_DEFAULT,
            help="Used in conjunction with end_index to determine the slice of records to be processed",
        )
        parser.add_argument(
            "--end-index",
            type=int,
            default=cls.END_INDEX_DEFAULT,
            help="Used in conjunction with start_index to determine the slice of records to be processed",
        )
        parser.add_argument(
            "--no-transaction",
            action="store_true",
            help="If given, no transaction will be used. WARNING: You should ensure "
            "that transactions are being managed elsewhere in order to prevent data loss!",
        )
        parser.add_argument(
            "-p",
            "--pattern",
            help=(
                "Regular expression used to identify Excel application files. "
                "Used only when a directory is given in path"
            ),
        )
        parser.add_argument(
            "--no-file-duplicate-check",
            action="store_true",
            help=(
                "This will skip the check for duplicate files, which "
                "will speed up the import significantly for large directories. "
                "But, behavior for handling duplicate files is... not ideal. "
                "So this should only be used after you are sure there are no duplicates!"
            ),
        )
        parser.add_argument(
            "--propagate",
            action="store_true",
            help=(
                "This will cause derived values to be derived and propagated "
                "as audit models are created. If not given, it is assumed that "
                "these will be derived at the end."
            ),
        )
        parser.add_argument(
            "--no-post-import-actions",
            action="store_true",
            help=(
                "If given, do not execute any of the defined post-import actions. "
                "This might be used if you plan on performing post-import actions yourself"
            ),
        )

        if cls.PROGRESS_TYPE == cls.PROGRESS_TYPES.ROW:
            parser.add_argument(
                "-r",
                "--rows",
                nargs="+",
                type=int,
                help="List of specific rows to process (by index)",
            )

        # TODO: Disallow no_transaction and dry_run being given
        # TODO: Enforce range on limit
        return parser

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+")
        self.add_core_arguments(parser)

    # TODO: This does NOT HANDLE duplicate headers! Behavior is not well
    # defined, and there WILL BE data loss if there are duplicate headers,
    # both with important information
    @staticmethod
    def load_rows(path):
        """Load rows from a CSV file"""
        with open(path, newline="", encoding="latin1") as file:
            lines = file.readlines()

        LOGGER.debug(f"Read {len(lines)} lines from {path}")
        return csv.DictReader(lines)

    def handle_record(self, record, file_import_attempt):
        """Provides logic for importing individual records"""

        raise NotImplementedError("Must be implemented by child class")

    def check_for_duplicates(self, paths):
        hash_to_path_map = defaultdict(list)
        tqdm.write("Checking for duplicates...")
        progress = tqdm(paths, unit="file")
        for path in progress:
            progress.desc = f"Hashing {path}"
            file_hash = hash_file(path)
            hash_to_path_map[file_hash].append(path)

        return {
            hash_: paths for hash_, paths in hash_to_path_map.items() if len(paths) > 1
        }

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

    def get_known_headers(self,):
        known_headers = set()
        for form_map in self.FORM_MAPS:
            known_headers.update(form_map.get_known_from_fields())
        return sorted(known_headers)

    def get_unmapped_headers(self, headers_to_check, known_headers):
        return [
            header
            for header in headers_to_check
            if header not in (*known_headers, *self.IGNORED_HEADERS)
        ]

    # TODO: This currently does nothing; see TODO on load_rows
    def get_duplicate_headers(self, headers_to_check, respect_ignored_headers=True):
        """Given an iterable of headers, return a dict of {header: num_duplicates}

        If no duplicates are found, an empty dict is returned"""

        if respect_ignored_headers:
            headers_to_check = [
                header
                for header in headers_to_check
                if header not in self.IGNORED_HEADERS
            ]
        return {
            header: headers_to_check.count(header)
            for header in headers_to_check
            if headers_to_check.count(header) > 1
        }

    def header_checks(self, headers):
        info = {}
        errors = {}

        # If some headers don't map to anything, report this as an error
        known_headers = self.get_known_headers()
        # Get ignored headers, if defined. Default to an empty list for later clarity
        ignored_headers = getattr(self, "IGNORED_HEADERS", [])
        info["ignored_headers"] = ignored_headers

        info["known_headers"] = known_headers
        unmapped_headers = self.get_unmapped_headers(headers, known_headers)

        if unmapped_headers:
            errors["unmapped_headers"] = unmapped_headers

        unmapped_header_ratio = len(unmapped_headers) / len(headers)
        # TODO: Store default somewhere else
        if unmapped_header_ratio > getattr(self, "THRESHOLD", 0.7):
            errors[
                "too_many_unmapped_headers"
            ] = f"{unmapped_header_ratio * 100:.2f}% of headers are not mapped"
        return info, errors

    def file_level_checks(self, rows):
        info = {}
        errors = {}
        if not rows:
            errors["empty"] = ["No rows!"]
            return info, errors

        headers = rows[0].keys()
        header_check_info, header_check_errors = self.header_checks(headers)

        info.update(header_check_info)
        errors.update(header_check_errors)

        return info, errors

    def handle_file(self, path, file_importer_batch, **options):
        LOGGER.debug(f"Handling path {path}")
        FileImporter = apps.get_model("django_import_data.FileImporter")
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        RowData = apps.get_model("django_import_data.RowData")
        # TODO: How to handle changes in path? That is, if a Batch file is moved
        # somewhere else we still need a way to force its association with the
        # existing Batch in the DB. Allow explicit Batch ID to be passed in?
        # Some other unique ID?
        current_command = self.__module__.split(".")[-1]
        try:
            file_modified_on = timezone.make_aware(
                datetime.fromtimestamp(os.path.getmtime(path))
            )
            hash_on_disk = hash_file(path)
            LOGGER.debug(f"Found {path}; hash: {hash_on_disk}")
        except FileNotFoundError:
            file_modified_on = None
            hash_on_disk = ""
            LOGGER.debug(f"{path} not found; using null hash and modification time")

        hash_checked_on = timezone.now()
        existing_file_importers = FileImporter.objects.filter(file_path=path)
        num_file_importers_found = existing_file_importers.count()
        if num_file_importers_found == 1:
            file_importer = existing_file_importers.first()
            LOGGER.debug(f"Found single existing FileImporter: FI {file_importer.id}")
            file_importer_created = False
            file_importer.hash_on_disk = hash_on_disk
            file_importer.hash_checked_on = hash_checked_on
            file_importer.file_importer_batch = file_importer_batch
            file_importer.save(
                propagate_derived_values=options["propagate"],
                derive_cached_values=options["propagate"],
            )
        elif num_file_importers_found == 0:
            file_importer = FileImporter.objects.create_fast(
                file_importer_batch=file_importer_batch,
                file_path=path,
                importer_name=current_command,
                file_modified_on=file_modified_on,
                hash_on_disk=hash_on_disk,
                hash_checked_on=hash_checked_on,
            )
            LOGGER.debug(
                f"Found no existing FileImporter; created FI {file_importer.id}"
            )
            file_importer_created = True
        else:
            raise ValueError(
                f">1 FIs found for {path}. This should be impossible "
                "due to unique constraint; something is very wrong"
            )

        file_importer.file_importer_batch = file_importer_batch
        file_importer.save(
            propagate_derived_values=options["propagate"],
            derive_cached_values=options["propagate"],
        )

        latest_file_import_attempt = file_importer.latest_file_import_attempt
        if latest_file_import_attempt:
            LOGGER.debug(
                f"Found previous FileImportAttempt: FIA {latest_file_import_attempt.id}"
            )
            if options["overwrite"] or options["skip"]:
                if options["skip"]:
                    LOGGER.debug(f"Skipping processing of {path}")
                    if self.verbosity > 2:
                        tqdm.write(
                            f"SKIPPING previous FIA: {latest_file_import_attempt}"
                        )
                    # TODO: We shouldn't return here...
                    return None
                else:
                    LOGGER.debug(
                        f"Overwriting previous FIA {latest_file_import_attempt.id}"
                    )
                    if self.verbosity > 2:
                        tqdm.write(
                            f"DELETING previous FIA: {latest_file_import_attempt}"
                        )
                    num_deletions, deletions = (
                        latest_file_import_attempt.delete_imported_models()
                    )
                    LOGGER.debug(
                        f"Deleted {num_deletions} models:\n{pformat(deletions)}"
                    )
                    if self.verbosity > 2:
                        tqdm.write(
                            f"Deleted {num_deletions} models:\n{pformat(deletions)}"
                        )
            else:
                raise ValueError(
                    f"Found previous File Import Attempt '{latest_file_import_attempt}', "
                    "but cannot delete or skip it due to lack of overwrite=True or skip=True!"
                )

        file_level_errors = {}
        try:
            rows = list(self.load_rows(path))
        except (FileNotFoundError, ValueError) as error:
            if options["durable"]:
                tqdm.write(f"ERROR: {error}")
                if "misc" in file_level_errors:
                    file_level_errors["misc"].append([error])
                else:
                    file_level_errors["misc"] = [error]
            else:
                raise ValueError("Error loading rows!") from error
            rows = []

        LOGGER.debug(f"Got {len(rows)} rows from {path}")
        file_level_info, more_file_level_errors = self.file_level_checks(rows)
        file_level_errors.update(more_file_level_errors)
        if not os.path.isfile(path):
            if "misc" in file_level_errors:
                file_level_errors["misc"].append(["file_missing"])
            else:
                file_level_errors["misc"] = ["file_missing"]
        if file_level_errors and not options["durable"]:
            raise ValueError(f"One or more file-level errors: {file_level_errors}")

        file_import_attempt = FileImportAttempt.objects.create(
            file_importer=file_importer,
            imported_from=path,
            info=file_level_info,
            errors=file_level_errors,
            imported_by=self.__module__,
            hash_when_imported=hash_on_disk,
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

        # TODO: Excel logic of adding a column with original row needs to be here, then removed there?
        # We start at 2 here:
        # +1 to make it 1-indexed (more intuitive for end user)
        # +1 to compensate for header being the first row
        # TODO: This is NOT robust across all use cases! Should be defined in the importer_spec.json/CLI, worst case...
        for ri, row in enumerate(rows, 2):
            row_data = RowData.objects.create(
                row_num=ri, data=row, file_import_attempt=file_import_attempt
            )
            self.handle_record(row_data, durable=options["durable"])
            errors = {
                model_importer.latest_model_import_attempt.imported_by: model_importer.latest_model_import_attempt.errors
                for model_importer in row_data.model_importers.all()
                if model_importer.latest_model_import_attempt.errors
            }
            if errors:
                error_str = (
                    f"Row {ri} of file {os.path.basename(path)} handled, but had {len(errors)} errors:\n"
                    f"{json.dumps(errors, indent=2)}"
                )
                if options["durable"]:
                    tqdm.write(error_str)
                else:
                    raise ValueError(error_str)

                all_errors.append(errors)

        creations, errors = self.summary(file_import_attempt, all_errors)
        file_import_attempt.creations = creations
        file_import_attempt.errors.update(errors)
        file_import_attempt.ignored_headers = self.IGNORED_HEADERS
        file_import_attempt.save(
            propagate_derived_values=options["propagate"],
            derive_cached_values=options["propagate"],
        )
        return file_import_attempt

        # raise ValueError("hmmm")

    def summary(self, file_import_attempt, all_errors):
        error_summary = {}
        total_form_errors = 0
        total_conversion_errors = 0
        creations = (
            file_import_attempt.row_datas.filter(
                model_importers__model_import_attempts__status__in=[2, 3]
            )
            .values(
                model=F("model_importers__model_import_attempts__content_type__model")
            )
            .annotate(
                creation_count=Count("model_importers__model_import_attempts__status")
            )
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
        if self.verbosity == 3:
            tqdm.write("=" * 80)
            tqdm.write("Model Import Summary:")
            for creation in creations:
                tqdm.write(
                    "Created {creation_count} {model} objects".format(**creation)
                )
            tqdm.write("-" * 80)
        if error_summary and self.verbosity > 1:
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

    def handle_files(self, files_to_process, **options):
        FileImporterBatch = apps.get_model("django_import_data.FileImporterBatch")
        current_command = self.__module__.split(".")[-1]
        # NOTE: Any future positional args will need to be popped out here, too
        paths = options.pop("paths")
        file_importer_batch = FileImporterBatch.objects.create(
            command=current_command, args=paths, kwargs=options
        )
        LOGGER.debug(
            f"Created FIB {file_importer_batch.id}; will process {files_to_process} {self.verbosity}"
        )
        for path in files_to_process:
            if self.verbosity == 3:
                tqdm.write(f"Processing {path}")
            file_import_attempt = self.handle_file(path, file_importer_batch, **options)
            # LOGGER.debug(
            #     f"handle_files: file_import_attempt: {file_import_attempt.id}; {file_import_attempt.file_importer.file_importer_batch.id}"
            # )
            assert file_import_attempt is not None

        return file_importer_batch

    def post_import_actions(self, file_importer_batch):
        LOGGER.debug("Performing post_import_actions")
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        ModelImporter = apps.get_model("django_import_data.ModelImporter")
        # Derive appropriate statuses for all MIs. This will also
        # propagate to all FIAs, FIs, and FIBs
        LOGGER.debug("Deriving status values for Model Importers")
        ModelImporter.objects.filter(
            row_data__file_import_attempt__file_importer__file_importer_batch__id=file_importer_batch.id
        ).derive_values()
        LOGGER.debug("Deriving status values for File Import Attempts")
        # TODO: Make this more robust via Managers instead of Querysets...
        # This is needed to check all FIAs without any MIs!
        FileImportAttempt.objects.filter(
            file_importer__file_importer_batch__id=file_importer_batch.id
        ).derive_values()

    def post_import_checks(self, file_importer_batch, **options):
        tqdm.write("All Batch-Level Errors")
        all_file_errors = [
            fi.latest_file_import_attempt.errors
            for fi in file_importer_batch.file_importers.all()
            if fi and fi.latest_file_import_attempt.errors
        ]

        unique_file_error_types = set(
            (key for e in all_file_errors for key in e.keys())
        )

        all_unique_errors = {}
        for error_type in unique_file_error_types:
            errors_by_file = [
                file_errors[error_type]
                for file_errors in all_file_errors
                if error_type in file_errors
            ]
            unique_errors = set(error for errors in errors_by_file for error in errors)
            all_unique_errors[error_type] = unique_errors

        file_importer_batch.errors.update(
            {key: list(value) for key, value in all_unique_errors.items()}
        )
        file_importer_batch.save(
            propagate_derived_values=options["propagate"],
            derive_cached_values=options["propagate"],
        )
        tqdm.write(pformat(all_unique_errors))
        tqdm.write("=" * 80)

    def handle(self, *args, **options):
        self.verbosity = options["verbosity"]
        try:
            files_to_process = determine_files_to_process(
                options["paths"], pattern=options["pattern"]
            )
        except ValueError as error:
            if options["durable"]:
                tqdm.write(f"ERROR: {error}")
                files_to_process = options["paths"]
            else:
                raise

        if not files_to_process:
            if options["durable"]:
                tqdm.write(f"ERROR: No files were found!")
                files_to_process = []
            else:
                raise ValueError("No files were found!")

        if self.PROGRESS_TYPE == self.PROGRESS_TYPES.FILE:
            files_to_process = self.determine_records_to_process(
                files_to_process,
                **{
                    option: value
                    for option, value in options.items()
                    if option in ["limit", "start_index", "end_index"]
                },
            )

        if not options["no_file_duplicate_check"]:
            duplicate_paths = self.check_for_duplicates(files_to_process)
            if duplicate_paths:
                num_duplicates = 0
                for duplicate_paths in duplicate_paths.values():
                    tqdm.write(f"Duplicate paths:")
                    for path in duplicate_paths:
                        num_duplicates += 1
                        tqdm.write(f"  {path}")
                        files_to_process.remove(path)
                if options["durable"]:
                    tqdm.write(
                        f"The above {num_duplicates} duplicate paths have been removed from the pending import!"
                    )
                else:
                    raise ValueError("Duplicate paths found! See log for details")

        if self.PROGRESS_TYPE == self.PROGRESS_TYPES.FILE:
            files_to_process = tqdm(files_to_process, desc=self.help, unit="files")

        if options["no_transaction"]:
            file_importer_batch = self.handle_files(files_to_process, **options)
        else:
            with transaction.atomic():
                file_importer_batch = self.handle_files(files_to_process, **options)

                if options["dry_run"]:
                    transaction.set_rollback(True)
                    tqdm.write("DRY RUN; rolling back changes")

        file_importer_batch.errors["duplicate_paths"] = duplicate_paths
        self.post_import_checks(file_importer_batch, **options)
        if not options["no_post_import_actions"]:
            self.post_import_actions(file_importer_batch)
        else:
            tqdm.write(
                "Skipping post import actions due to presence of no_post_import_actions=True"
            )
