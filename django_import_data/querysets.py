"""Querysets for django_import_data"""

from datetime import datetime
import os

from tqdm import tqdm

from django.apps import apps
from django.db import transaction
from django.db.models import F, OuterRef, Subquery
from django.db.models.query import QuerySet
from django.utils.timezone import make_aware, now

from .utils import hash_file


class DerivedValuesQueryset(QuerySet):
    @transaction.atomic
    def derive_values(self, propagate_derived_values=True):
        for instance in tqdm(self, unit=self.model._meta.verbose_name):
            instance.save(propagate_derived_values=False)

        if propagate_derived_values and hasattr(self, "propagate_derived_values"):
            self.propagate_derived_values()


class FileImportBatchQuerySet(DerivedValuesQueryset):
    pass


class FileImporterQuerySet(DerivedValuesQueryset):
    def refresh_from_filesystem(self):
        """Recompute the hash_on_disk fields of all QuerySet members

        Returns a report of which members are missing, changed, or unchanged
        from the previous import check"""
        report = {"missing": [], "changed": [], "unchanged": []}
        progress = tqdm(self.order_by("created_on"), unit="files")
        for file_importer in progress:
            file_importer.hash_checked_on = now()
            path = file_importer.file_path
            progress.desc = path
            try:
                hash_on_disk = hash_file(path)
            except FileNotFoundError:
                file_importer.hash_on_disk = ""
                file_importer.save()
                report["missing"].append(file_importer)
            else:
                file_modified_on = make_aware(
                    datetime.fromtimestamp(os.path.getmtime(path))
                )
                if file_importer.hash_on_disk != hash_on_disk:
                    report["changed"].append(file_importer)
                else:
                    report["unchanged"].append(file_importer)
                file_importer.hash_on_disk = hash_on_disk
                file_importer.file_modified_on = file_modified_on
                file_importer.save()

        return report

    def changed_files(self):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        FileImporter = apps.get_model("django_import_data.FileImporter")
        latest = FileImportAttempt.objects.filter(
            file_importer=OuterRef("pk")
        ).order_by("-created_on")
        changed_hashes = FileImporter.objects.annotate(
            latest_hash=Subquery(latest.values("hash_when_imported")[:1])
        ).exclude(hash_on_disk=F("latest_hash"))

        changed_paths = FileImporter.objects.filter(hash_on_disk="")

        changed = changed_hashes | changed_paths
        return changed


class FileImportAttemptQuerySet(DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        FileImportBatch = apps.get_model("django_import_data.FileImportBatch")
        FileImporter = apps.get_model("django_import_data.FileImporter")
        FileImportBatch.objects.filter(
            file_import_attempts__in=self.values("id")
        ).distinct().derive_values()
        FileImporter.objects.filter(
            file_import_attempts__in=self.values("id")
        ).distinct().derive_values()

    @transaction.atomic
    def update(self, *args, propagate_derived_values=True, **kwargs):
        result = super().update(*args, **kwargs)
        propagated_fields_being_updated = [
            field for field in self.model.PROPAGATED_FIELDS if field in kwargs.keys()
        ]
        if propagate_derived_values and propagated_fields_being_updated:
            tqdm.write(
                "Now propagating derived values because the following "
                f"propagated fields are being updated: {propagated_fields_being_updated}. "
                "To disable this behavior, use propagate_derived_values=False"
            )
            self.propagate_derived_values()

        return result


class ModelImportAttemptQuerySet(DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        FileImportAttempt.objects.filter(
            model_import_attempts__in=self.values("id")
        ).distinct().derive_values()

    @transaction.atomic
    def update(self, *args, propagate_derived_values=True, **kwargs):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")

        result = super().update(*args, **kwargs)
        propagated_fields_being_updated = [
            field for field in self.model.PROPAGATED_FIELDS if field in kwargs.keys()
        ]
        if propagate_derived_values and propagated_fields_being_updated:
            tqdm.write(
                "Now propagating derived values because the following "
                f"propagated fields are being updated: {propagated_fields_being_updated}. "
                "To disable this behavior, use propagate_derived_values=False"
            )
            self.propagate_derived_values()

        return result
