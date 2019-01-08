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
    auditee_fields = JSONField(encoder=DjangoErrorJSONEncoder, null=True)
    errors = JSONField(encoder=DjangoErrorJSONEncoder, null=True)
    error_summary = JSONField(encoder=DjangoErrorJSONEncoder, null=True)
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


class GenericAuditGroup(BaseAuditGroup):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True)
    auditee = GenericForeignKey()

    class Meta:
        # Can't enforce uniqueness on auditee, but this is effectively the
        # same (and actually works)
        unique_together = (("content_type", "object_id"),)

    def __str__(self):
        return f"Audit Group for {self.content_type} {self.auditee} ({self.status})"

    def get_absolute_url(self):
        return reverse("genericauditgroup_detail", args=[str(self.id)])


class GenericAudit(BaseAudit):
    audit_group = models.ForeignKey(
        GenericAuditGroup, related_name="audits", on_delete=models.CASCADE
    )

    def get_absolute_url(self):
        return reverse("genericaudit_detail", args=[str(self.id)])


class AuditedModel(models.Model):
    audit_groups = GenericRelation(GenericAuditGroup)
    # objects = GenericAuditManager()

    class Meta:
        abstract = True

    # audit_groups is actually a 1:1 relationship, so we
    # can safely make audit_group available like this
    # for the sake of convenience
    @cached_property
    def audit_group(self):
        return self.audit_groups.first()
