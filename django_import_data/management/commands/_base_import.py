import csv

# from pprint import pformat
import json
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from tqdm import tqdm


class BaseImportCommand(BaseCommand):
    @staticmethod
    def add_core_arguments(parser):
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
        rows = list(self.load_rows(path))
        limit = options.get("limit", None)
        if limit is not None:
            rows = self.get_random_rows(rows, limit)

        for row in tqdm(rows, desc=self.help, unit="rows"):
            try:
                audits = self.handle_row(row)
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
                    error_str = f"Row handled, but had {len(errors)} errors:\n{json.dumps(errors, indent=2)}"
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
