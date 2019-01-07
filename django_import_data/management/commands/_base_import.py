import csv
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tqdm import tqdm


class BaseImportCommand(BaseCommand):
    def add_arguments(self, parser):
        # TODO: Allow multiple paths for all importers
        parser.add_argument("path")
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
        parser.add_argument("-l", "--limit", type=float)

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

        for row in tqdm(rows, unit="rows"):
            try:
                audits = self.handle_row(row)
            except Exception as error:
                tqdm.write(f"Failed to handle row: {row}")
                if not durable:
                    raise error
                tqdm.write(str(error))

            errors = {field: audit.errors for field, audit in audits.items() if audit}
            if errors and not durable:
                raise ValueError(f"{len(errors)} errors in row: {errors}")

    @transaction.atomic
    def handle(self, *args, **options):
        print(args)
        print(options)
        self.handle_rows(*args, **options)
        if options["dry_run"]:
            transaction.set_rollback = True
            print("DRY RUN; rolling back changes")
