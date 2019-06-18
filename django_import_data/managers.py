from datetime import datetime
import os

from tqdm import tqdm

from django.apps import apps
from django.db.models import OuterRef, Subquery
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.timezone import make_aware, now

from .utils import hash_file


class ModelImportAttemptManager(models.Manager):
    def create_for_model(self, model, **kwargs):
        return self.create(
            content_type=ContentType.objects.get_for_model(model), **kwargs
        )


class FileImporterManager(models.Manager):
    def create_with_attempt(self, path, errors=None):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        file_importer = self.create()
        file_import_attempt = FileImportAttempt.objects.create(
            imported_from=path, file_importer=file_importer, errors=errors
        )
        return file_importer, file_import_attempt

    def get_queryset(self):
        return FileImporterQuerySet(self.model, using=self._db)


class FileImporterQuerySet(models.query.QuerySet):
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

        print(report)
        return report

    def changed_files(self):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        FileImporter = apps.get_model("django_import_data.FileImporter")
        latest = FileImportAttempt.objects.filter(
            file_importer=OuterRef("pk")
        ).order_by("-created_on")
        changed_hashes = FileImporter.objects.annotate(
            latest_hash=Subquery(latest.values("hash_when_imported")[:1])
        ).exclude(hash_on_disk=models.F("latest_hash"))

        changed_paths = FileImporter.objects.filter(hash_on_disk="")

        changed = changed_hashes | changed_paths
        return changed
