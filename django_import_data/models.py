import os

from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

from .mixins import ImportStatusModel, TrackedModel


class DjangoErrorJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Exception, GEOSGeometry)):
            return repr(obj)

        return super().default(obj)


# Change to: BaseImporterBatch
class BaseAuditGroupBatch(TrackedModel, ImportStatusModel):
    """Represents a "batch" of Audit Groups imported from the same file"""

    # TODO: Reconsider unique
    # TODO: Reconsider existence -- if cached_property used then this wouldn't be needed?
    last_imported_path = models.CharField(max_length=512, unique=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Batch {self.name}"

    @property
    def most_recent_import(self):
        return self.imports.order_by("created_on").last()

    @cached_property
    def name(self):
        return os.path.basename(self.last_imported_path)


# Change to: BatchImporterBatch
class GenericAuditGroupBatch(BaseAuditGroupBatch):
    class Meta:
        ordering = ["-created_on"]
        verbose_name = "Generic Audit Group Batch"
        verbose_name_plural = "Generic Audit Group Batches"

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

    def __str__(self):
        return f"Batch Import {self.name}"

    def save(self, *args, **kwargs):
        # print("GBI save")
        self.batch.status = self.status
        self.batch.last_imported_path = self.imported_from
        self.batch.save()
        super().save(*args, **kwargs)

    @cached_property
    def name(self):
        return os.path.basename(self.imported_from)


class GenericBatchImport(BaseBatchImport):
    class Meta:
        ordering = ["-created_on"]
        verbose_name = "Generic Batch Import"
        verbose_name_plural = "Generic Batch Imports"

    def get_absolute_url(self):
        return reverse("genericbatchimport_detail", args=[str(self.id)])

    # TODO: Remove this!
    @property
    def audit_groups(self):
        return self.genericauditgroup_audit_groups


# Change to: BaseImporter
class BaseAuditGroup(TrackedModel, ImportStatusModel):
    """Groups a set of Audits together"""

    row_data = models.ForeignKey(
        "django_import_data.RowData",
        related_name="%(class)s_audit_groups",
        on_delete=models.CASCADE,
        help_text="Reference to the original data used to create this audit group",
    )
    form_map = models.CharField(max_length=64)
    importee_class = models.CharField(max_length=64)

    class Meta:
        abstract = True

    @cached_property
    def name(self):
        if "FormMap" not in self.form_map:
            return self.form_map
        return self.form_map[: len(self.form_map) - len("FormMap")].lower()


# Change to: BaseImportAttempt
class BaseAudit(TrackedModel, ImportStatusModel):
    importer = NotImplemented
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
        # print("GA save")
        if self.errors:
            self.status = "rejected"
        else:
            self.status = "created_clean"

        # The status of an importer should always be that status of its
        # most recent import attempt
        self.importer.status = self.status
        self.importer.save()

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
        # print("thing", thing)
        return thing

    class Meta:
        verbose_name = "Row Data"
        verbose_name_plural = "Row Data"

    # def __str__(self):
    #     return f"Row data for models: {self.get_audited_models()}"

    def get_absolute_url(self):
        return reverse("rowdata_detail", args=[str(self.id)])


# Change to: Importer
class GenericAuditGroup(BaseAuditGroup):
    batch_import = models.ForeignKey(
        GenericBatchImport,
        related_name="%(class)s_audit_groups",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Reference to the batch import this was created from",
    )

    class Meta:
        verbose_name = "Generic Audit Group"
        verbose_name_plural = "Generic Audit Groups"

    def __str__(self):
        if self.importee:
            importee_str = self.importee
        else:
            importee_str = self.importee_class

        return f"Audit Group for {importee_str} ({self.status})"

    def save(self, *args, **kwargs):
        # print("GAG save")
        super().save(*args, **kwargs)
        if self.batch_import:
            if self.STATUSES[self.batch_import.status] < self.STATUSES[self.status]:
                self.batch_import.status = self.status
                self.batch_import.save()

    def get_absolute_url(self):
        return reverse("genericauditgroup_detail", args=[str(self.id)])

    def get_create_from_audit_url(self):
        audit = self.audits.last()
        return audit.get_create_from_audit_url()

    def attempt(self, **kwargs):
        kwargs["audit_group"] = kwargs.pop("importer")
        return GenericAudit.objects.create(**kwargs)

    def get_populated_related_objects(self):
        return [
            ro
            for ro in self._meta.related_objects
            if issubclass(ro.related_model, AuditedModel) and hasattr(self, ro.name)
        ]

    # @cached_property
    # def importee_name(self):
    #     if not self.importee:
    #         return self.importee_class.__name__
    #     return self.importee._meta.verbose_name

    # @cached_property
    # def importee_class(self):
    #     ros = self.get_populated_related_objects()
    #     if not ros:
    #         return None
    #     assert len(ros) == 1, "There shouldn't be multiple populated related querysets"
    #     return ros[0].related_model

    @cached_property
    def importee(self):
        ros = [getattr(self, ro.name) for ro in self.get_populated_related_objects()]
        if not ros:
            return None
        assert len(ros) == 1, "There shouldn't be multiple populated related querysets"
        return ros[0]


# Change to: BaseImportAttempt
class GenericAudit(BaseAudit):
    audit_group = models.ForeignKey(
        GenericAuditGroup,
        related_name="audits",
        on_delete=models.CASCADE,
        help_text="Reference to the audit group that 'holds' this audit",
    )

    class Meta:
        verbose_name = "Generic Audit"
        verbose_name_plural = "Generic Audits"

    def get_absolute_url(self):
        return reverse("genericaudit_detail", args=[str(self.id)])

    def get_create_from_audit_url(self):
        return reverse(
            f"{self.audit_group.importee_class}_create_from_audit".lower(),
            args=[str(self.id)],
        )

    @property
    def importer(self):
        return self.audit_group


class AuditedModel(models.Model):
    # This can't be OneToOne because it's possible that more than one
    # instance of a given model will be created from a given row
    # row_data = models.ForeignKey(
    #     RowData,
    #     related_name="%(class)s_models",
    #     on_delete=models.CASCADE,
    #     help_text="Reference to the original data used to create this model",
    # )
    # audit_groups = GenericRelation(
    #     GenericAuditGroup,
    #     help_text="Reference to the audit group that stores audit history regarding this model",
    #     # TODO: Still not sure how to use this
    #     related_query_name="models",
    # )
    # objects = GenericAuditManager()

    audit_group = models.OneToOneField(GenericAuditGroup, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    # audit_groups is actually a 1:1 relationship, so we
    # can safely make audit_group available like this
    # for the sake of convenience
    # @cached_property
    # def audit_group(self):
    #     return self.audit_groups.first()
