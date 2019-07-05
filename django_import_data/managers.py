import os

from tqdm import tqdm

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .querysets import (
    FileImportAttemptQuerySet,
    FileImporterBatchQuerySet,
    FileImporterQuerySet,
    ModelImportAttemptQuerySet,
    ModelImporterQuerySet,
)


class ModelImporterManager(models.Manager):
    def create_with_attempt(self, model, file_import_attempt, errors=None, **kwargs):
        ModelImportAttempt = apps.get_model("django_import_data.ModelImportAttempt")
        model_importer = self.create(file_import_attempt=file_import_attempt)
        model_import_attempt = ModelImportAttempt.objects.create_for_model(
            model=model, model_importer=model_importer, errors=errors, **kwargs
        )
        return model_importer, model_import_attempt

    def get_queryset(self):
        return ModelImporterQuerySet(self.model, using=self._db)


class ModelImportAttemptManager(models.Manager):
    def create_for_model(self, model, **kwargs):
        content_type = ContentType.objects.get_for_model(model)
        model_import_attempt = self.create(content_type=content_type, **kwargs)
        # model.model_import_attempt = model_import_attempt
        # model.save()
        return model_import_attempt

    def get_queryset(self):
        return ModelImportAttemptQuerySet(self.model, using=self._db)


class FileImporterBatchManager(models.Manager):
    def get_queryset(self):
        return FileImporterBatchQuerySet(self.model, using=self._db)


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
