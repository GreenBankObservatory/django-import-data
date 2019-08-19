"""Querysets for django_import_data"""

from collections import defaultdict

from tqdm import tqdm

from django.apps import apps
from django.db import transaction
from django.db.models import F, OuterRef, Subquery, Count, Q
from django.db.models.query import QuerySet


class TrackedFileQueryset(QuerySet):
    """Contains operations for synchronizing with files on disk"""

    # Note: we don't need this to be atomic
    def refresh_from_filesystem(self, always_hash=False, quiet=False):
        """Recompute the hash_on_disk fields of all QuerySet members

        Returns a report of which members are missing, changed, or unchanged
        from the previous import check"""
        report = defaultdict(list)
        progress = tqdm(self.order_by("created_on"), unit="files", disable=quiet)
        for instance in progress:
            # progress.desc = instance.file_path
            status = instance.refresh_from_filesystem(always_hash=always_hash)
            report[status].append(instance)

        return report


class DerivedValuesQueryset(QuerySet):
    @transaction.atomic
    def derive_values(self, propagate_derived_values=True):
        for instance in tqdm(self, unit=self.model._meta.verbose_name):
            # Derive any necessary values for the model, but don't propagate them!
            instance.save(derive_cached_values=True, propagate_derived_values=False)

        # Now we propagate them, all at once, at the end
        if propagate_derived_values and hasattr(self, "propagate_derived_values"):
            tqdm.write(f"Propagating saved values from {self.__class__}")
            self.propagate_derived_values()

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


class FileImporterBatchQuerySet(DerivedValuesQueryset):
    def annotate_num_file_importers(self):
        return self.annotate(num_file_importers=Count("file_importers", distinct=True))

    def annotate_num_successful_file_importers(self):
        FileImporterBatch = apps.get_model("django_import_data.FileImporterBatch")
        return self.annotate(
            num_successful_file_importers=Count(
                "file_importers",
                distinct=True,
                filter=Q(status=FileImporterBatch.STATUSES.created_clean.db_value),
            )
        )

    def annotate_num_failed_file_importers(self):
        FileImporterBatch = apps.get_model("django_import_data.FileImporterBatch")
        return self.annotate(
            num_failed_file_importers=Count(
                "file_importers",
                distinct=True,
                filter=Q(
                    status__in=[
                        status.db_value
                        for status in FileImporterBatch.STATUSES
                        if status != FileImporterBatch.STATUSES.created_clean
                    ]
                ),
            )
        )


class FileImporterQuerySet(TrackedFileQueryset, DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        FileImporterBatch = apps.get_model("django_import_data.FileImporterBatch")
        FileImporterBatch.objects.filter(
            file_importers__in=self.values("id")
        ).distinct().derive_values()

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

    def annotate_current_status(self):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        current_status = (
            FileImportAttempt.objects.filter(file_importer=OuterRef("pk"))
            .order_by("-created_on")
            .values("current_status")[:1]
        )
        return self.annotate(current_status=Subquery(current_status))

    def annotate_num_file_import_attempts(self):
        return self.annotate(
            num_file_import_attempts=Count("file_import_attempts", distinct=True)
        )

    def annotate_num_row_datas(self):
        return self.annotate(
            num_row_datas=Count(
                "file_import_attempts__row_datas",
                filter=Q(
                    file_import_attempts__row_datas__file_import_attempt__file_importer__id=F(
                        "id"
                    )
                ),
                distinct=True,
            )
        )

    def annotate_num_model_importers(self):
        return self.annotate(
            num_model_importers=Count(
                "file_import_attempts__row_datas__model_importers",
                filter=Q(
                    file_import_attempts__row_datas__file_import_attempt__file_importer__id=F(
                        "id"
                    )
                ),
                distinct=True,
            )
        )


class RowDataQuerySet(DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        FileImportAttempt.objects.filter(
            row_datas__in=self.values("id")
        ).distinct().derive_values()

    def annotate_num_model_importers(self):
        return self.annotate(
            num_model_importers=Count("model_importers", distinct=True)
        )

    def annotate_current_status(self):
        return self.annotate(current_status=F("file_import_attempt__current_status"))


class ModelImporterQuerySet(DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        RowData = apps.get_model("django_import_data.RowData")
        RowData.objects.filter(
            model_importers__in=self.values("id")
        ).distinct().derive_values()

    def annotate_num_model_import_attempts(self):
        return self.annotate(
            num_model_import_attempts=Count("model_import_attempts", distinct=True)
        )

    def annotate_num_successful(self):
        FileImporterBatch = apps.get_model("django_import_data.FileImporterBatch")
        return self.annotate(
            num_successful_file_importers=Count(
                "file_importers",
                distinct=True,
                filter=Q(status=FileImporterBatch.STATUSES.created_clean.db_value),
            )
        )

    def annotate_num_failed(self):
        FileImporterBatch = apps.get_model("django_import_data.FileImporterBatch")
        return self.annotate(
            num_failed_file_importers=Count(
                "file_importers",
                distinct=True,
                filter=Q(
                    status__in=[
                        status.db_value
                        for status in FileImporterBatch.STATUSES
                        if status != FileImporterBatch.STATUSES.created_clean
                    ]
                ),
            )
        )

    def annotate_current_status(self):
        return self.annotate(
            current_status=F("row_data__file_import_attempt__current_status")
        )


class FileImportAttemptQuerySet(DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        FileImporter = apps.get_model("django_import_data.FileImporter")
        FileImporter.objects.filter(
            file_import_attempts__in=self.values("id")
        ).distinct().derive_values()

    def annotate_num_model_importers(self):
        return self.annotate(
            num_model_importers=Count("row_datas__model_importers", distinct=True)
        )


class ModelImportAttemptQuerySet(DerivedValuesQueryset):
    @transaction.atomic
    def propagate_derived_values(self):
        ModelImporter = apps.get_model("django_import_data.ModelImporter")

        ModelImporter.objects.filter(
            id__in=self.values("id")
        ).distinct().derive_values()

    def annotate_current_status(self):
        return self.annotate(
            current_status=F(
                "model_importer__row_data__file_import_attempt__current_status"
            )
        )
