import json

from django.urls import reverse
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from django.contrib.contenttypes.models import ContentType

from .mixins import TrackedModel
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.utils.functional import cached_property
from django.conf import settings


class DjangoErrorJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Exception):
            return repr(obj)
        return super().default(obj)


class BaseAuditGroup(TrackedModel):
    """Groups a set of ObjectAudits together

    """

    # auditee = NotImplemented
    status = models.CharField(
        max_length=16,
        choices=(
            ("rejected", "Rejected: Fatal Errors"),
            ("created_dirty", "Imported: Some Errors"),
            ("created_clean", "Imported: No Errors"),
            ("pending", "Pending"),
        ),
        default="pending",
    )

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


class BaseAudit(TrackedModel):
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
    status = models.CharField(
        max_length=16,
        choices=(
            ("rejected", "Rejected: Fatal Errors"),
            ("created_dirty", "Imported: Some Errors"),
            ("created_clean", "Imported: No Errors"),
            ("pending", "Pending"),
        ),
        default="pending",
        help_text="The import status of the auditee",
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
        "was originally encountered"
    )

    # TODO: Surely there's a better, canonical way of doing this?
    def get_audited_models(self):
        """Return all AuditedModel instances associated with this model

        That is, return all model instances that were created from this row data
        """

        # Get a list of field (attribute) names from associated AuditedModel
        # instances
        fields = [
            field.name
            for field in self._meta.get_fields()
            if field.related_model and issubclass(field.related_model, AuditedModel)
        ]
        # Now get the queryset for each of these fields and join them all together
        models = []
        for field in fields:
            models.extend(getattr(self, field).all())
        return models

    def __str__(self):
        return f"Row data for models: {self.get_audited_models()}"

    def get_absolute_url(self):
        return reverse("rowaudit_detail", args=[str(self.id)])


class GenericAuditGroup(BaseAuditGroup):
    row_data = models.ForeignKey(
        RowData,
        related_name="audits",
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

    def get_absolute_url(self):
        return reverse("genericauditgroup_detail", args=[str(self.id)])


class GenericAudit(BaseAudit):
    audit_group = models.ForeignKey(
        GenericAuditGroup,
        related_name="audits",
        on_delete=models.CASCADE,
        help_text="Reference to the audit group that 'holds' this audit",
    )

    def get_absolute_url(self):
        return reverse("genericaudit_detail", args=[str(self.id)])


class AuditedModel(models.Model):
    # This can't be OneToOne because it's possible that more than one
    # instance of a given model will be created from a given row
    row_data = models.ForeignKey(
        RowData,
        related_name="%(class)s_models",
        on_delete=models.CASCADE,
        help_text="Reference to the original data used to create this model",
    )
    audit_groups = GenericRelation(
        GenericAuditGroup,
        help_text="Reference to the audit group that stores audit history regarding this model",
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
