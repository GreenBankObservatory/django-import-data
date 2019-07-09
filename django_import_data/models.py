"""Django Import Data Models"""

from collections import Counter
from importlib import import_module
import os
from pprint import pformat

from tqdm import tqdm

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

from .mixins import ImportStatusModel, TrackedModel
from .utils import DjangoErrorJSONEncoder
from .managers import (
    ModelImportAttemptManager,
    ModelImporterManager,
    FileImporterManager,
    FileImportAttemptManager,
    FileImporterBatchManager,
    RowDataManager,
)

### ABSTRACT BASE CLASSES ###
class RowData(ImportStatusModel, models.Model):
    file_import_attempt = models.ForeignKey(
        "django_import_data.FileImportAttempt",
        on_delete=models.CASCADE,
        related_name="row_datas",
    )
    data = JSONField(
        help_text="Stores a 'row' (or similar construct) of data as it "
        "was originally encountered",
        encoder=DjangoJSONEncoder,
    )
    row_num = models.PositiveIntegerField()
    headers = JSONField(null=True)
    errors = JSONField(null=True, default=dict)

    objects = RowDataManager()

    def __str__(self):
        return (
            f"Row {self.row_num} from '{self.file_import_attempt.name}' via "
            f"'{self.file_import_attempt.importer_name}'"
        )

    class Meta:
        verbose_name = "Row Data"
        verbose_name_plural = "Row Data"

    def get_absolute_url(self):
        return reverse("rowdata_detail", args=[str(self.id)])

    def derive_status(self):
        """RD status is the most severe status of its MIs"""
        if self.model_importers.exists():
            status = (
                self.model_importers.order_by("-status")
                .values_list("status", flat=True)
                .first()
            )
        else:
            status = self.STATUSES.empty.db_value

        return status

    def derive_cached_values(self):
        self.status = self.derive_status()

    def save(
        self, *args, derive_cached_values=True, propagate_derived_values=True, **kwargs
    ):
        if derive_cached_values:
            self.derive_cached_values()
        super().save(*args, **kwargs)

        if propagate_derived_values:
            self.file_import_attempt.save(
                propagate_derived_values=propagate_derived_values
            )


class AbstractBaseFileImporterBatch(ImportStatusModel, TrackedModel):

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

    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this FIB"""

        total_num_fi_deletions = 0
        total_num_fia_deletions = 0
        total_num_mia_deletions = 0
        all_mia_deletions = Counter()
        # For every ContentType imported by this FIB...
        for fi in self.file_importers.all():
            # ...and delete them:
            num_fia_deletions, num_mia_deletions, all_mia_deletions = (
                fi.delete_imported_models()
            )
            total_num_fi_deletions += 1
            total_num_fia_deletions += num_fia_deletions
            total_num_mia_deletions += num_mia_deletions
            all_mia_deletions += all_mia_deletions

        self.status = ImportStatusModel.STATUSES.deleted
        self.save()

        return (total_num_fia_deletions, total_num_mia_deletions, all_mia_deletions)

    @transaction.atomic
    def reimport(self, paths=None):
        """Delete then reimport all models imported by this FIB"""
        if paths is not None:
            args = paths
        else:
            args = self.args
        num_fias_deleted, num_models_deleted, deletions = self.delete_imported_models()
        call_command(self.command, *args, **{**self.kwargs, "overwrite": True})
        return FileImporterBatch.objects.order_by("created_on").last()

    def derive_status(self):
        """FIB status is the most severe status of its most recent FIs"""
        if self.file_importers.exists():
            status = (
                self.file_importers.order_by("-status")
                .values_list("status", flat=True)
                .first()
            )
        else:
            status = self.STATUSES.empty.db_value
        return status

    def derive_cached_values(self):
        self.status = self.derive_status()

    def save(
        self, *args, derive_cached_values=True, propagate_derived_values=True, **kwargs
    ):
        if derive_cached_values:
            self.derive_cached_values()

        super().save(*args, **kwargs)


class AbstractBaseFileImporter(ImportStatusModel, TrackedModel):
    """Representation of all attempts to import a specific file"""

    file_importer_batch = NotImplemented

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

    def acknowledge(self):
        fia = self.latest_file_import_attempt
        fia.acknowledged = True
        fia.save()

    def unacknowledge(self):
        fia = self.latest_file_import_attempt
        fia.acknowledged = False
        fia.save()

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

    def derive_status(self):
        """FI status is the status of its most recent FIA"""
        if self.file_import_attempts.exists():
            status = (
                self.file_import_attempts.order_by("-created_on")
                .values_list("status", flat=True)
                .first()
            )
        else:
            status = self.STATUSES.empty.db_value
        return status

    def derive_cached_values(self):
        self.status = self.derive_status()

    def save(
        self, *args, derive_cached_values=True, propagate_derived_values=True, **kwargs
    ):
        if derive_cached_values:
            self.derive_cached_values()

        super().save(*args, **kwargs)

        if propagate_derived_values:
            self.file_importer_batch.save(
                propagate_derived_values=propagate_derived_values
            )

    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this FI"""

        total_num_fia_deletions = 0
        total_num_mia_deletions = 0
        all_mia_deletions = Counter()
        # For every ContentType imported by this FI...
        for fia in self.file_import_attempts.all():
            # ...and delete them:
            num_fia_deletions, fia_deletions = fia.delete_imported_models()
            total_num_fia_deletions += 1
            total_num_mia_deletions += num_fia_deletions
            all_mia_deletions += fia_deletions

        self.status = ImportStatusModel.STATUSES.deleted.db_value
        self.save(derive_cached_values=False)

        return (total_num_fia_deletions, total_num_mia_deletions, all_mia_deletions)


class AbstractBaseFileImportAttempt(ImportStatusModel, TrackedModel):
    """Represents an individual attempt at an import of a "batch" of Importers"""

    PROPAGATED_FIELDS = ("status",)

    file_importer = NotImplemented

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
        return f"{self.name} <{self.importer_name}>"

    @property
    def importer_name(self):
        return self.imported_by.split(".")[-1]

    def derive_status(self):
        """FIA status is the most severe status of its RDs"""
        if self.row_datas.exists():
            status = (
                self.row_datas.order_by("-status")
                .values_list("status", flat=True)
                .first()
            )
        else:
            status = self.STATUSES.empty.db_value

        return status

    def derive_cached_values(self):
        self.status = self.derive_status()

    def save(
        self, *args, derive_cached_values=True, propagate_derived_values=True, **kwargs
    ):
        if derive_cached_values:
            self.derive_cached_values()
        super().save(*args, **kwargs)

        if propagate_derived_values:
            self.file_importer.save(propagate_derived_values=propagate_derived_values)

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
            id__in=self.row_datas.values(
                "model_importers__model_import_attempts__content_type"
            )
        ).distinct():

            try:
                # ...get a queryset of all model instances that were imported...
                to_delete = ct.model_class().objects.filter(
                    model_import_attempt__model_importer__row_data__file_import_attempt=self
                )
            except FieldError:
                # TODO: Warning?
                raise
            else:
                # ...and delete them:
                num_deletions_for_model_class, deletions_for_model_class = (
                    to_delete.delete()
                )
                num_deletions += num_deletions_for_model_class
                deletions += deletions_for_model_class
        # mia = (
        #     self.row_datas.order_by("created_on")
        #     .last()
        #     .latest_model_import_attempt
        # )
        # mia.status = ImportStatusModel.STATUSES.deleted.db_value
        # mia.save()

        self.status = ImportStatusModel.STATUSES.deleted.db_value
        self.save()
        return (num_deletions, deletions)

    def get_form_maps_used_during_import(self):
        return import_module(f"{self.imported_by}").Command.FORM_MAPS

    def get_field_maps_used_during_import(self):
        form_maps = self.get_field_maps_used_during_import()
        return {form_map.get_name(): form_map.field_maps for form_map in form_maps}


class AbstractBaseModelImporter(ImportStatusModel, TrackedModel):
    """Representation of all attempts to import a specific file"""

    row_data = models.ForeignKey(
        RowData,
        related_name="model_importers",
        on_delete=models.CASCADE,
        help_text="Reference to the original data used to create this audit group",
    )

    class Meta:
        abstract = True

    @property
    def latest_model_import_attempt(self):
        return self.model_import_attempts.order_by("created_on").last()

    @property
    def importee_class(self):
        return self.latest_model_import_attempt.importee_class

    def derive_status(self):
        """MI status is the status of its most recent MIA"""
        if self.model_import_attempts.exists():
            status = (
                self.model_import_attempts.order_by("-created_on")
                .values_list("status", flat=True)
                .first()
            )
        else:
            status = self.STATUSES.empty.db_value
        return status

    def derive_cached_values(self):
        self.status = self.derive_status()

    def save(
        self, *args, derive_cached_values=True, propagate_derived_values=True, **kwargs
    ):
        if derive_cached_values:
            self.derive_cached_values()

        super().save(*args, **kwargs)

        if propagate_derived_values:
            self.file_import_attempt.save(
                propagate_derived_values=propagate_derived_values
            )

    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this MI"""

        total_num_mia_deletions = 0
        # For every ContentType imported by this MI...
        for mia in self.model_import_attempts.all():
            # ...and delete them:
            num_mia_deletions, mia_deletions = mia.delete_imported_models()
            total_num_mia_deletions += num_mia_deletions

        self.status = ImportStatusModel.STATUSES.deleted.db_value
        self.save()
        return total_num_mia_deletions


###


class AbstractBaseModelImportAttempt(TrackedModel, ImportStatusModel):
    PROPAGATED_FIELDS = ("status",)

    importee_field_data = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        help_text="The original data used to create this Audit",
    )
    errors = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        help_text="Stores any errors encountered during the creation of the auditee",
    )
    error_summary = JSONField(
        encoder=DjangoErrorJSONEncoder,
        default=dict,
        help_text="Stores any 'summary' information that might need to be associated",
    )
    imported_by = models.CharField(max_length=128, default=None)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    # file_import_attempt = models.ForeignKey(
    #     "django_import_data.FileImportAttempt",
    #     related_name="model_import_attempts",
    #     on_delete=models.CASCADE,
    #     null=True,
    #     blank=True,
    #     help_text="Reference to the FileImportAttempt this was created from",
    # )

    model_importer = models.ForeignKey(
        "django_import_data.ModelImporter",
        related_name="model_import_attempts",
        on_delete=models.CASCADE,
        help_text="Reference to the ModelImporter that made this attempt",
    )

    @property
    def row_data(self):
        return self.model_importer.row_data

    @property
    def file_import_attempt(self):
        return self.model_importer.row_data.file_import_attempt

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    def __str__(self):
        if self.file_import_attempt:
            return (
                f"{self.content_type} imported from "
                f"{os.path.basename(self.imported_from)} ({self.STATUSES[self.status].value})"
            )

        return f"{self.content_type}: {self.STATUSES[self.status].value}"

    def save(
        self, *args, propagate_derived_values=True, derive_cached_values=False, **kwargs
    ):
        if self.status == ImportStatusModel.STATUSES.pending.db_value:
            if self.errors:
                self.status = ImportStatusModel.STATUSES.rejected.db_value
            else:
                self.status = ImportStatusModel.STATUSES.created_clean.db_value

        super().save(*args, **kwargs)
        if propagate_derived_values and self.file_import_attempt:
            self.file_import_attempt.save(
                propagate_derived_values=propagate_derived_values
            )
            self.model_importer.save(propagate_derived_values=propagate_derived_values)

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
            file_path=self.file_import_attempt.imported_from
            if self.file_import_attempt
            else None,
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
        return (
            self.file_import_attempt.imported_from if self.file_import_attempt else None
        )

    # TODO: UNIt tests!
    @transaction.atomic
    def delete_imported_models(self):
        """Delete all models imported by this MIA"""

        self.status = ImportStatusModel.STATUSES.deleted.db_value
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

    def gen_error_summary(self):
        summary_items = set()
        for conversion_error in self.errors.get("conversion_errors", []):
            summary_items.update(conversion_error["to_fields"])

        for form_error in self.errors.get("form_errors", []):
            summary_items.add(form_error["field"])

        return summary_items


### CONCRETE CLASSES ###


class FileImporterBatch(AbstractBaseFileImporterBatch):
    def get_absolute_url(self):
        return reverse("fileimporterbatch_detail", args=[str(self.id)])

    objects = FileImporterBatchManager()

    class Meta:
        verbose_name = "File Importer Batch"
        verbose_name_plural = "File Importer Batches"
        ordering = ["-created_on"]


class FileImporter(AbstractBaseFileImporter):
    file_importer_batch = models.ForeignKey(
        FileImporterBatch,
        related_name="file_importers",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
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
    file_importer = models.ForeignKey(
        FileImporter, related_name="file_import_attempts", on_delete=models.CASCADE
    )

    objects = FileImportAttemptManager()

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "File Import Attempt"
        verbose_name_plural = "File Import Attempts"

    def get_absolute_url(self):
        return reverse("fileimportattempt_detail", args=[str(self.id)])


class ModelImporter(AbstractBaseModelImporter):
    objects = ModelImporterManager()

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "Model Importer"
        verbose_name_plural = "Model Importers"

    def get_absolute_url(self):
        return reverse("modelimporter_detail", args=[str(self.id)])

    # def gen_import(self, path):
    #     return ModelImportAttempt.objects.create(batch=self, imported_from=path)


class ModelImportAttempt(AbstractBaseModelImportAttempt):
    # NOTE: We override this here to give it a more sensible related_name
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


### MODEL MIXINS ###


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
