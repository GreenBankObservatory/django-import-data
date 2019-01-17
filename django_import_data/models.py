"""Django Import Data Models"""

import os
from pprint import pformat

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

from .mixins import ImportStatusModel, TrackedModel
from .utils import DjangoErrorJSONEncoder


### ABSTRACT BASE CLASSES ###
class RowData(models.Model):
    file_import_attempt = models.ForeignKey(
        "django_import_data.FileImportAttempt",
        on_delete=models.CASCADE,
        related_name="rows",
    )
    data = JSONField(
        help_text="Stores a 'row' (or similar construct) of data as it "
        "was originally encountered",
        encoder=DjangoJSONEncoder,
    )

    # TODO: Surely there's a better, canonical way of doing this?
    def get_audited_models(self):
        """Return all AbstractBaseAuditedModel instances associated with this model

        That is, return all model instances that were created from this row data
        """
        model_importers = []
        if hasattr(self, "model_importers"):
            model_importers.extend(self.genericauditgroup_model_importers.all())
        thing = [ag.auditee for ag in model_importers if ag.auditee]
        # print("thing", thing)
        return thing

    class Meta:
        verbose_name = "Row Data"
        verbose_name_plural = "Row Data"

    def summary(self):
        return f"Row data for models: {self.get_audited_models()}"

    def get_absolute_url(self):
        return reverse("rowdata_detail", args=[str(self.id)])

    # def status(self):
    #     return self.import_attempts.filter(status="rejected").exists()


class AbstractBaseFileImporter(TrackedModel, ImportStatusModel):
    """Representation of all attempts to import a specific file"""

    # TODO: Reconsider unique
    # TODO: Reconsider existence -- if cached_property used then this wouldn't be needed?
    last_imported_path = models.CharField(max_length=512, unique=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"File Importer for {self.name}"

    @property
    def most_recent_import(self):
        return self.imports.order_by("created_on").last()

    @cached_property
    def name(self):
        return os.path.basename(self.last_imported_path)


class AbstractBaseFileImportAttempt(TrackedModel, ImportStatusModel):
    """Represents an individual attempt at an import of a "batch" of Importers"""

    file_importer = NotImplemented

    # TODO: Make this a FileField?
    imported_from = models.CharField(
        max_length=512,
        default=None,
        help_text="Path to file that this was imported from",
    )
    creations = JSONField(encoder=DjangoErrorJSONEncoder, default=dict, null=True)
    errors = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        null=True,
        help_text="Stores any file-level errors encountered during import",
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name}: {self.get_status_display()}"

    def save(self, *args, propagate_status=True, **kwargs):
        if propagate_status and self.file_importer:
            self.file_importer.status = self.status
            self.file_importer.last_imported_path = self.imported_from
            self.file_importer.save()
        super().save(*args, **kwargs)

    @cached_property
    def name(self):
        return os.path.basename(self.imported_from)


class AbstractBaseModelImportAttempt(TrackedModel, ImportStatusModel):
    # TODO: This MAYBE can be here
    row_data = models.ForeignKey(
        RowData,
        related_name="%(class)s_attempts",
        on_delete=models.CASCADE,
        help_text="Reference to the original data used to create this audit group",
    )

    importee_field_data = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        # null=True,
        # blank=True,
        help_text="The original data used to create this Audit",
    )
    errors = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        # null=True,
        # blank=True,
        help_text="Stores any errors encountered during the creation of the auditee",
    )
    error_summary = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        # null=True,
        # blank=True,
        help_text="Stores any 'summary' information that might need to be associated",
    )
    imported_from = models.CharField(max_length=512)
    imported_by = models.CharField(max_length=128)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # IF GFK
    # object_id = models.PositiveIntegerField(null=True)
    # importee = GenericForeignKey()

    file_import_attempt = models.ForeignKey(
        "django_import_data.FileImportAttempt",
        related_name="model_import_attempts",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Reference to the FileImportAttempt this was created from",
    )

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    def __str__(self):
        return (
            f"{self.content_type} imported from "
            f"{os.path.basename(self.imported_from)} ({self.get_status_display()})"
        )

    def save(self, *args, propagate_status=True, **kwargs):
        if self.errors:
            self.status = ImportStatusModel.STATUSES.rejected.name
        else:
            self.status = ImportStatusModel.STATUSES.created_clean.name

        if propagate_status and self.file_import_attempt:
            if (
                self.STATUSES[self.file_import_attempt.status]
                < self.STATUSES[self.status]
            ):
                self.file_import_attempt.status = self.status
                self.file_import_attempt.save()
        super().save(*args, **kwargs)

    def summary(self):
        return (
            "I {created_str} a(n) {importee_class} instance {importee_str}from "
            "data {importee_field_data} I converted from row {row_data}, which "
            "I found in file {file_path}"
        ).format(
            created_str="created" if self.importee else "attempted to create",
            importee_class=self.importee_class.__name__,
            importee_str=f"({self.importee}) " if self.importee else "",
            importee_field_data=pformat(self.importee_field_data),
            row_data=pformat(self.row_data.data),
            file_path=self.file_import_attempt.imported_from,
        )

    @property
    def importee_class(self):
        return self.content_type.model_class()

    # IF NO GFK
    @property
    def importee(self):
        """Get the object we are auditing, if it exists, otherwise return None"""
        return getattr(self, self.content_type.model, None)

    # IF NO GFK
    @importee.setter
    def importee(self, instance):
        """Set auditee to given object"""
        return setattr(self, self.content_type.model, instance)


### CONCRETE CLASSES ###


class FileImporterManager(models.Manager):
    def create_with_attempt(self, path, errors=None):
        fi = self.create(last_imported_path=path)
        fia = FileImportAttempt.objects.create(
            imported_from=path, file_importer=fi, errors=errors
        )
        return fi, fia


class FileImporter(AbstractBaseFileImporter):
    objects = FileImporterManager()

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "File Importer"
        verbose_name_plural = "File Importers"

    def get_absolute_url(self):
        return reverse("fileimporter_detail", args=[str(self.id)])

    def gen_import(self, path):
        return FileImportAttempt.objects.create(batch=self, imported_from=path)


class FileImportAttempt(AbstractBaseFileImportAttempt):
    # TODO: Just importer?
    file_importer = models.ForeignKey(
        FileImporter, related_name="import_attempts", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "File Import Attempt"
        verbose_name_plural = "File Import Attempts"

    def get_absolute_url(self):
        return reverse("fileimportattempt_detail", args=[str(self.id)])


class ModelImportAttemptManager(models.Manager):
    def create_for_model(self, model, **kwargs):
        return self.create(
            content_type=ContentType.objects.get_for_model(model), **kwargs
        )


class ModelImportAttempt(AbstractBaseModelImportAttempt):
    # NOTE: We override this here to give it a more sensible related_name
    row_data = models.ForeignKey(
        RowData,
        related_name="import_attempts",
        on_delete=models.CASCADE,
        help_text="Reference to the original data used to create this audit group",
    )
    objects = ModelImportAttemptManager()

    class Meta:
        verbose_name = "Model Import Attempt"
        verbose_name_plural = "Model Import Attempts"

    def get_absolute_url(self):
        return reverse("modelimportattempt_detail", args=[str(self.id)])

    def get_create_from_import_attempt_url(self):
        return reverse(
            f"{self.content_type.model}_create_from_audit", args=[str(self.id)]
        )

    def delete(self, *args, **kwargs):
        if self.importee:
            num_importee_deletions, importee_deletions = self.importee.delete()
        num_deletions, deletions = super().delete(*args, **kwargs)
        return (
            num_deletions + num_importee_deletions,
            {**deletions, **importee_deletions},
        )


### MODEL MIXINS ###


# class AuditedModelManager(models.Manager):
#     def create_with_audit(self, model_kwargs, audit_kwargs):
#         model = self.model(**model_kwargs)
#         audit = ModelImportAttempt.objects.create_for_model(**audit_kwargs)
#         model.model_import_attempt = audit
#         model.save()
#         return model, audit


class AbstractBaseAuditedModel(models.Model):
    # NO GFK
    model_import_attempt = models.OneToOneField(
        ModelImportAttempt, on_delete=models.CASCADE, unique=True, null=True, blank=True
    )
    # IF GFK
    # model_import_attempts = GenericRelation(
    #     ModelImportAttempt, related_query_name="%(class)s_imported_models"
    # )

    # objects = AuditedModelManager()

    # IF GFK
    # @property
    # def model_import_attempt(self):
    #     return self.model_import_attempts.first()

    # IF GFK
    # @model_import_attempt.setter
    # def model_import_attempt(self, instance):
    #     return self.model_import_attempts.set([instance])

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if (
            self.model_import_attempt
            and self.model_import_attempt.importee_class != self.__class__
        ):
            raise ValueError(
                "Mismatched importee class designations! "
                f"Our class ({self.__class__}) differs from "
                "self.model_import_attempt.importee_class "
                f"({self.model_import_attempt.importee_class}! "
            )

        super().save(*args, **kwargs)
