import json
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
    RowDataQuerySet,
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

    def get_successful(self):
        return self.filter(
            status__in=[
                self.model.STATUSES.created_clean.db_value,
                self.model.STATUSES.created_dirty.db_value,
            ]
        )

    def get_rejected(self):
        return self.filter(
            status__in=[
                self.model.STATUSES.rejected.db_value,
                self.model.STATUSES.empty.db_value,
            ]
        )

    def get_num_successful(self):
        return self.get_successful().count()

    def get_num_rejected(self):
        return self.get_rejected().count()


class RowDataManager(DerivedValuesManager):
    def get_queryset(self):
        return RowDataQuerySet(self.model, using=self._db)


class ModelImporterManager(DerivedValuesManager):
    def create_with_attempt(
        self,
        model,
        row_data,
        errors=None,
        derive_cached_values=False,
        propagate_derived_values=False,
        **kwargs,
    ):
        ModelImportAttempt = apps.get_model("django_import_data.ModelImportAttempt")
        model_importer = self.create(row_data=row_data)
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
        imported_by,
        derive_cached_values=False,
        propagate_derived_values=False,
        **kwargs,
    ):
        content_type = ContentType.objects.get_for_model(model)
        model_import_attempt = self.create(
            derive_cached_values=derive_cached_values,
            propagate_derived_values=propagate_derived_values,
            content_type=content_type,
            imported_by=imported_by,
            **kwargs,
        )
        return model_import_attempt

    def get_queryset(self):
        return ModelImportAttemptQuerySet(self.model, using=self._db)

    def with_importee(self):
        queryset = self.none()
        for model_name in self.values_list("content_type__model", flat=True):
            queryset |= self.filter(**{f"{model_name}__isnull": False})
        return queryset

    def without_importee(self):
        queryset = self.exclude(id__in=self.with_importee().values("id"))
        return queryset

    def get_num_with_importee(self):
        return self.with_importee().count()

    def get_num_without_importee(self):
        return self.without_importee().count()


class FileImporterBatchManager(DerivedValuesManager):
    def get_queryset(self):
        return FileImporterBatchQuerySet(self.model, using=self._db)


class FileImportAttemptManager(DerivedValuesManager):
    def get_queryset(self):
        return FileImportAttemptQuerySet(self.model, using=self._db)


class FileImporterManager(DerivedValuesManager):
    def create_with_attempt(self, path, importer_name, errors=None):
        FileImportAttempt = apps.get_model("django_import_data.FileImportAttempt")
        file_importer = self.create(importer_name=importer_name, file_path=path)
        file_import_attempt = FileImportAttempt.objects.create(
            imported_from=path, file_importer=file_importer, errors=errors
        )
        return file_importer, file_import_attempt

    def get_queryset(self):
        return FileImporterQuerySet(self.model, using=self._db)
