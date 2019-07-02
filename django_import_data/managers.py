import os

from tqdm import tqdm

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .querysets import (
    ModelImportAttemptQuerySet,
    FileImportAttemptQuerySet,
    FileImportBatchQuerySet,
    FileImporterQuerySet,
)


class ModelImportAttemptManager(models.Manager):
    def create_for_model(self, model, **kwargs):
        return self.create(
            content_type=ContentType.objects.get_for_model(model), **kwargs
        )

    def get_queryset(self):
        return ModelImportAttemptQuerySet(self.model, using=self._db)


class FileImportBatchManager(models.Manager):
    def get_queryset(self):
        return FileImportBatchQuerySet(self.model, using=self._db)


class FileImportAttemptManager(models.Manager):
    def get_queryset(self):
        return FileImportAttemptQuerySet(self.model, using=self._db)


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
