"""Django Import Data Models"""

from collections import Counter
from importlib import import_module
import os
from pprint import pformat

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField, JSONField
from django.core.exceptions import FieldError
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db import transaction
from django.urls import reverse
from django.utils.functional import cached_property

from .mixins import IsActiveModel, ImportStatusModel, TrackedModel
from .utils import DjangoErrorJSONEncoder
from .managers import ModelImportAttemptManager, FileImporterManager

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
    row_num = models.PositiveIntegerField()
    headers = JSONField(null=True)
    errors = JSONField(null=True, default=dict)

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


class AbstractBaseFileImportBatch(TrackedModel, ImportStatusModel):
    command = models.CharField(max_length=64, default=None)
    args = ArrayField(models.CharField(max_length=256))
    kwargs = JSONField()
    errors = JSONField(null=True, default=dict)

    @cached_property
    def cli(self):
        clean_options = {}
        for key, value in self.kwargs.items():
            if key not in (
                "settings",
                "start_index",
                "traceback",
                "verbosity",
                "skip_checks",
                "no_color",
                "pythonpath",
            ):
                if isinstance(value, list):
                    value = " ".join(value)

                if isinstance(key, str):
                    key = key.replace("_", "-")

                clean_options[key] = value

        importer_name = self.command
        args_str = " ".join(self.args)
        options_str = ""
        for key, value in clean_options.items():
            if isinstance(value, bool):
                if value:
                    options_str += f" --{key}"
            elif value is not None:
                options_str += f" --{key} {value}"
        return f"python manage.py {importer_name} {args_str}{options_str}"

    class Meta:
        abstract = True

    def __str__(self):
        return self.cli

    @property
    def is_active(self):
        """FIB is active as long as any of its import attempts are still active"""
        return self.file_import_attempts.filter(is_active=True).exists()

    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this FIB"""

        total_num_fia_deletions = 0
        total_num_mia_deletions = 0
        all_mia_deletions = Counter()
        # For every ContentType imported by this FIB...
        for fia in self.file_import_attempts.all():
            # ...and delete them:
            num_fia_deletions, fia_deletions = fia.delete_imported_models()
            total_num_fia_deletions += 1
            total_num_mia_deletions += num_fia_deletions
            all_mia_deletions += fia_deletions

        return (total_num_fia_deletions, total_num_mia_deletions, all_mia_deletions)

    @transaction.atomic
    def reimport(self, paths=None):
        """Delete then reimport all models imported by this FIB"""
        if paths is not None:
            args = paths
        else:
            args = self.args
        num_fias_deleted, num_models_deleted, deletions = self.delete_imported_models()
        print(num_fias_deleted, num_models_deleted, deletions)
        call_command(self.command, *args, **{**self.kwargs, "overwrite": True})
        return FileImportBatch.objects.first()


class AbstractBaseFileImporter(TrackedModel, ImportStatusModel):
    """Representation of all attempts to import a specific file"""

    file_path = models.CharField(
        max_length=512,
        default=None,
        help_text="Path to the file that this imports",
        unique=True,
    )
    importer_name = models.CharField(
        max_length=128, default=None, help_text="The name of the Importer to use"
    )
    hash_on_disk = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text="SHA-1 hash of the file on disk. If blank, the file is missing",
    )
    file_modified_on = models.DateTimeField(null=True, blank=True)
    hash_checked_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"File Importer for {self.name}"

    @property
    def latest_file_import_attempt(self):
        return self.file_import_attempts.order_by("created_on").last()

    @property
    def name(self):
        return os.path.basename(self.file_path)

    @property
    def acknowledged(self):
        """Return True if all FIAs have been acknowledged; otherwise False"""

        return not self.file_import_attempts.filter(acknowledged=False).exists()

    @acknowledged.setter
    def acknowledged(self, value):
        self.file_import_attempts.update(acknowledged=value)

    @property
    def is_active(self):
        """FI is active as long as any of its import attempts are still active"""
        return self.model_import_attempts.filter(is_active=True).exists()

    def reimport(self):
        return call_command(
            self.importer_name,
            self.latest_file_import_attempt.imported_from,
            overwrite=True,
            durable=True,
        )

    @property
    def file_missing(self):
        return self.hash_on_disk == ""

    @property
    def file_changed(self):
        return self.hash_on_disk != self.latest_file_import_attempt.hash_when_imported


class AbstractBaseFileImportAttempt(TrackedModel, ImportStatusModel):
    """Represents an individual attempt at an import of a "batch" of Importers"""

    file_importer = NotImplemented
    file_import_batch = NotImplemented

    # TODO: Make this a FileField?
    imported_from = models.CharField(
        max_length=512,
        default=None,
        help_text="Path to file that this was imported from",
    )
    imported_by = models.CharField(max_length=128, null=True)
    creations = JSONField(encoder=DjangoErrorJSONEncoder, default=dict, null=True)
    info = JSONField(
        default=dict, null=True, help_text="Stores any file-level info about the import"
    )
    errors = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        null=True,
        help_text="Stores any file-level errors encountered during import",
    )
    acknowledged = models.BooleanField(default=False)
    ignored_headers = ArrayField(
        models.CharField(max_length=128),
        null=True,
        blank=True,
        help_text="Headers that were ignored during import",
    )
    hash_when_imported = models.CharField(max_length=40, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name}: {self.get_status_display()}"

    def save(self, *args, propagate_status=True, **kwargs):
        print("errors", self.errors)
        if self.status == "created_clean" and self.errors:
            self.status = "created_dirty"
        elif "misc" in self.errors and "file_missing" in self.errors["misc"]:
            self.status = "rejected"
        if propagate_status and self.file_importer:
            self.file_importer.status = self.status
            self.file_importer.save()
        if propagate_status and self.file_import_batch:
            if (
                self.STATUSES[self.status]
                > self.STATUSES[self.file_import_batch.status]
            ):
                self.file_import_batch.status = self.status
                self.file_import_batch.save()

        super().save(*args, **kwargs)
        print("wtf", self.status)

    @cached_property
    def name(self):
        return os.path.basename(self.imported_from)

    # TODO: Unit tests!
    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this FIA"""

        num_deletions = 0
        deletions = Counter()
        # For every ContentType imported by this FIA...
        for ct in ContentType.objects.filter(
            id__in=self.model_import_attempts.values("content_type")
        ):
            try:
                # ...get a queryset of all model instances that were imported...
                to_delete = ct.model_class().objects.filter(
                    model_import_attempt__file_import_attempt=self
                )
            except FieldError:
                # TODO: Warning?
                pass
            else:
                # ...and delete them:
                num_deletions_for_model_class, deletions_for_model_class = (
                    to_delete.delete()
                )
                num_deletions += num_deletions_for_model_class
                deletions += deletions_for_model_class

        return (num_deletions, deletions)

    def get_form_maps_used_during_import(self):
        return import_module(f"{self.imported_by}").Command.FORM_MAPS

    def get_field_maps_used_during_import(self):
        form_maps = self.get_field_maps_used_during_import()
        return {form_map.get_name(): form_map.field_maps for form_map in form_maps}

    @property
    def is_active(self):
        """FIA is active as long as any of its import attempts are still active"""
        return self.model_import_attempts.filter(is_active=True).exists()


class AbstractBaseModelImportAttempt(IsActiveModel, TrackedModel, ImportStatusModel):
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
    imported_by = models.CharField(max_length=128, default=None)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    acknowledged = models.BooleanField(default=False)

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
                self.STATUSES[self.status]
                > self.STATUSES[self.file_import_attempt.status]
            ):
                # print(
                #     f"Set FIA status from {self.file_import_attempt.status} to {self.status}"
                # )
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

    @cached_property
    def imported_from(self):
        return self.file_import_attempt.imported_from

    # TODO: UNIt tests!
    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this MIA"""

        self.is_active = False
        self.save()

        num_deletions = 0
        deletions = Counter()
        # For every ContentType imported by this MIA...
        for ct in ContentType.objects.filter(id__in=self.values("content_type")):
            # ...get a queryset of all model instances that were imported...
            to_delete = ct.model_class().objects.filter(model_import_attempt=self)
            # ...and delete them:
            num_deletions_for_model_class, deletions_for_model_class = (
                to_delete.delete()
            )
            num_deletions += num_deletions_for_model_class
            deletions += deletions_for_model_class
        return (num_deletions, deletions)


### CONCRETE CLASSES ###


class FileImportBatch(AbstractBaseFileImportBatch):
    def get_absolute_url(self):
        return reverse("fileimportbatch_detail", args=[str(self.id)])

    class Meta:
        verbose_name = "File Import Batch"
        verbose_name_plural = "File Import Batches"
        ordering = ["-created_on"]


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
        FileImporter, related_name="file_import_attempts", on_delete=models.CASCADE
    )
    file_import_batch = models.ForeignKey(
        FileImportBatch, related_name="file_import_attempts", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "File Import Attempt"
        verbose_name_plural = "File Import Attempts"

    def get_absolute_url(self):
        return reverse("fileimportattempt_detail", args=[str(self.id)])


class ModelImportAttempt(AbstractBaseModelImportAttempt):
    # NOTE: We override this here to give it a more sensible related_name
    row_data = models.ForeignKey(
        RowData,
        related_name="model_import_attempts",
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
            getattr(self, "model_import_attempt", None)
            and self.model_import_attempt.importee_class != self.__class__
        ):
            raise ValueError(
                "Mismatched importee class designations! "
                f"Our class ({self.__class__}) differs from "
                "self.model_import_attempt.importee_class "
                f"({self.model_import_attempt.importee_class}! "
            )

        super().save(*args, **kwargs)

    @cached_property
    def imported_from(self):
        try:
            return self.model_import_attempt.file_import_attempt.imported_from
        except AttributeError:
            return None
