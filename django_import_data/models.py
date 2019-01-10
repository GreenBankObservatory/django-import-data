import json
import os

from django.urls import reverse
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.utils.functional import cached_property
from django.contrib.gis.geos import GEOSGeometry

from .mixins import ImportStatusModel, TrackedModel


class DjangoErrorJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Exception, GEOSGeometry)):
            return repr(obj)

        return super().default(obj)


class BaseAuditGroupBatch(TrackedModel, ImportStatusModel):
    """Represents a "batch" of Audit Groups imported from the same file"""

    # TODO: Reconsider unique
    # TODO: Reconsider existence -- if cached_property used then this wouldn't be needed?
    last_imported_path = models.CharField(max_length=512, unique=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    def __str__(self):
        return f"Batch {os.path.basename(self.last_imported_path)}"

    @property
    def most_recent_import(self):
        return self.imports.order_by("created_on").last()


class GenericAuditGroupBatch(BaseAuditGroupBatch):
    def get_absolute_url(self):
        return reverse("genericauditgroupbatch_detail", args=[str(self.id)])

    def gen_import(self, path):
        return GenericBatchImport.objects.create(batch=self, imported_from=path)


class BaseBatchImport(TrackedModel, ImportStatusModel):
    """Represents an individual attempt at an import of a "batch" of Audit Groups"""

    batch = models.ForeignKey(
        GenericAuditGroupBatch, related_name="imports", on_delete=models.CASCADE
    )
    # TODO: Make this a FileField?
    imported_from = models.CharField(
        max_length=512, help_text="Path to file that this batch was imported from"
    )
    errors = JSONField(
        encoder=DjangoErrorJSONEncoder,
        null=True,
        blank=True,
        help_text="Stores any batch/file-level errors encountered during import",
    )

    class Meta:
        abstract = True
        verbose_name = "Batch Import"
        verbose_name_plural = "Batch Imports"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Batch Import {os.path.basename(self.imported_from)}"

    def save(self, *args, **kwargs):
        self.batch.status = self.status
        self.batch.last_imported_path = self.imported_from
        self.batch.save()
        super().save(*args, **kwargs)


class GenericBatchImport(BaseBatchImport):
    def get_absolute_url(self):
        return reverse("genericbatchimport_detail", args=[str(self.id)])

    def summary(self):
        return {
            ag.content_type.model: ag.status
            for ag in self.genericauditgroup_audit_groups.all()
        }

    # TODO: Remove this!
    @property
    def audit_groups(self):
        return self.genericauditgroup_audit_groups


class BaseAuditGroup(TrackedModel, ImportStatusModel):
    """Groups a set of Audits together"""

    form_map = models.CharField(max_length=64)

    @cached_property
    def name(self):
        if "FormMap" not in self.form_map:
            return self.form_map
        return self.form_map[: len(self.form_map) - len("FormMap")].lower()

    class Meta:
        abstract = True


# class GenericAuditManager(models.Manager):
#     def create_with_audit(self, *args, **kwargs):
#         auditee = self.create(*args, **kwargs)
#         GenericAuditGroup.objects.get_or_create(
#             content_type=ContentType.objects.get_for_model(auditee),
#             object_id=auditee.id,
#         )

#         return auditee


class BaseAudit(TrackedModel, ImportStatusModel):
    audit_group = NotImplemented
    auditee_fields = JSONField(
        encoder=DjangoErrorJSONEncoder,
        null=True,
        help_text="The original data used to create this Audit",
    )
    errors = JSONField(
        encoder=DjangoErrorJSONEncoder,
        null=True,
        help_text="Stores any errors encountered during the creation of the auditee",
    )
    error_summary = JSONField(
        encoder=DjangoErrorJSONEncoder,
        null=True,
        help_text="Stores any 'summary' information that might need to be associated",
    )
    imported_from = models.CharField(max_length=512)

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    def save(self, *args, **kwargs):
        # if self.audit_group and self.audit_group.auditee:
        #     auditee = self.audit_group.auditee
        #     raise ValueError(
        #         f"There already exists a {auditee._meta.model.__name__} "
        #         f"for this audit group: {auditee}"
        #     )
        # TODO: This is a little weird, but alright...
        if self.errors:
            self.status = "rejected"
        else:
            self.status = "created_clean"
        self.audit_group.status = self.status
        # self.audit_group.last_imported_path = self.imported_from
        self.audit_group.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Audit {self.created_on} {self.imported_from} ({self.status})"


class RowData(models.Model):
    data = JSONField(
        help_text="Stores a 'row' (or similar construct) of data as it "
        "was originally encountered",
        encoder=DjangoJSONEncoder,
    )

    # TODO: Surely there's a better, canonical way of doing this?
    def get_audited_models(self):
        """Return all AuditedModel instances associated with this model

        That is, return all model instances that were created from this row data
        """

        # Get a list of field (attribute) names from associated AuditedModel
        # instances
        # fields = [
        #     field.name
        #     for field in self._meta.get_fields()
        #     if field.related_model and issubclass(field.related_model, AuditedModel)
        # ]
        # # Now get the queryset for each of these fields and join them all together
        # models = []
        # for field in fields:
        #     models.extend(getattr(self, field).all())
        # return models
        audit_groups = []
        if hasattr(self, "audit_groups"):
            audit_groups.extend(self.genericauditgroup_audit_groups.all())
        thing = [ag.auditee for ag in audit_groups if ag.auditee]
        print("thing", thing)
        return thing

    # def __str__(self):
    #     return f"Row data for models: {self.get_audited_models()}"

    def get_absolute_url(self):
        return reverse("rowdata_detail", args=[str(self.id)])


class GenericAuditGroup(BaseAuditGroup):
    batch_import = models.ForeignKey(
        GenericBatchImport,
        related_name="%(class)s_audit_groups",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Reference to the batch import this was created from",
    )
    row_data = models.ForeignKey(
        "django_import_data.RowData",
        related_name="%(class)s_audit_groups",
        on_delete=models.CASCADE,
        help_text="Reference to the original data used to create this audit group",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True)
    auditee = GenericForeignKey()

    class Meta:
        # Can't enforce uniqueness on auditee, but this is effectively the
        # same (and actually works)
        unique_together = (("content_type", "object_id"),)
        # This should provide a big performance gain (I think), because
        # we will very frequently be querying based on these (as opposed to ID)
        indexes = (models.Index(fields=("content_type", "object_id")),)

    def __str__(self):
        if self.auditee:
            return f"Audit Group for {self.content_type} {self.auditee} ({self.status})"

        return f"Audit Group for {self.content_type} ({self.status})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.batch_import:
            self.batch_import.status = self.status
            self.batch_import.save()

    def get_absolute_url(self):
        return reverse("genericauditgroup_detail", args=[str(self.id)])

    def get_create_from_audit_url(self):
        audit = self.audits.last()
        return audit.get_create_from_audit_url()


class GenericAudit(BaseAudit):
    audit_group = models.ForeignKey(
        GenericAuditGroup,
        related_name="audits",
        on_delete=models.CASCADE,
        help_text="Reference to the audit group that 'holds' this audit",
    )

    def get_absolute_url(self):
        return reverse("genericaudit_detail", args=[str(self.id)])

    def get_create_from_audit_url(self):
        return reverse(
            f"{self.audit_group.content_type.model}_create_from_audit",
            args=[str(self.id)],
        )


class AuditedModel(models.Model):
    # This can't be OneToOne because it's possible that more than one
    # instance of a given model will be created from a given row
    # row_data = models.ForeignKey(
    #     RowData,
    #     related_name="%(class)s_models",
    #     on_delete=models.CASCADE,
    #     help_text="Reference to the original data used to create this model",
    # )
    audit_groups = GenericRelation(
        GenericAuditGroup,
        help_text="Reference to the audit group that stores audit history regarding this model",
        # TODO: Still not sure how to use this
        related_query_name="models",
    )
    # objects = GenericAuditManager()

    class Meta:
        abstract = True

    # audit_groups is actually a 1:1 relationship, so we
    # can safely make audit_group available like this
    # for the sake of convenience
    @cached_property
    def audit_group(self):
        return self.audit_groups.first()
