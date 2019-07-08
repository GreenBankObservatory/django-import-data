import os

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


class DerivedValuesManager(models.Manager):
    def create_fast(self, *args, **kwargs):
        return self.create(
            *args, **kwargs, derive_cached_values=False, propagate_derived_values=False
        )

    def create(
        self,
        *args,
        derive_cached_values=False,
        propagate_derived_values=False,
        **kwargs,
    ):
        instance = self.model(*args, **kwargs)
        instance.save(
            derive_cached_values=derive_cached_values,
            propagate_derived_values=propagate_derived_values,
        )
        return instance


class ModelImporterManager(DerivedValuesManager):
    def create_with_attempt(
        self,
        model,
        file_import_attempt,
        errors=None,
        derive_cached_values=False,
        propagate_derived_values=False,
        **kwargs,
    ):
        ModelImportAttempt = apps.get_model("django_import_data.ModelImportAttempt")
        model_importer = self.create(file_import_attempt=file_import_attempt)
        model_import_attempt = ModelImportAttempt.objects.create_for_model(
            model=model,
            model_importer=model_importer,
            errors=errors,
            derive_cached_values=derive_cached_values,
            propagate_derived_values=propagate_derived_values,
            **kwargs,
        )
        return model_importer, model_import_attempt

    def get_queryset(self):
        return ModelImporterQuerySet(self.model, using=self._db)


class ModelImportAttemptManager(DerivedValuesManager):
    def create_for_model(
        self,
        model,
        derive_cached_values=False,
        propagate_derived_values=False,
        **kwargs,
    ):
        content_type = ContentType.objects.get_for_model(model)
        model_import_attempt = self.create(
            derive_cached_values=derive_cached_values,
            propagate_derived_values=propagate_derived_values,
            content_type=content_type,
            **kwargs,
        )
        return model_import_attempt

    def get_queryset(self):
        return ModelImportAttemptQuerySet(self.model, using=self._db)


class FileImporterBatchManager(DerivedValuesManager):
    def get_queryset(self):
        return FileImporterBatchQuerySet(self.model, using=self._db)


class FileImportAttemptManager(DerivedValuesManager):
    def get_queryset(self):
        return FileImportAttemptQuerySet(self.model, using=self._db)


class FileImporterManager(DerivedValuesManager):
    def create_with_attempt(self, path, errors=None):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        file_importer = self.create()
        file_import_attempt = FileImportAttempt.objects.create(
            imported_from=path, file_importer=file_importer, errors=errors
        )
        return file_importer, file_import_attempt

    def get_queryset(self):
        return FileImporterQuerySet(self.model, using=self._db)
