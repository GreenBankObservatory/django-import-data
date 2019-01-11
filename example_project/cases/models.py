from django.db import models
from django.urls import reverse

from django_import_data.models import AuditedModel
from django_import_data.models import (
    BaseAudit,
    BaseAuditGroup,
    BaseBatchImport,
    BaseAuditGroupBatch,
)


class Person(AuditedModel):
    name = models.CharField(max_length=256, blank=True)
    phone = models.CharField(max_length=256, blank=True)
    email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}; {self.phone}; {self.email}"

    def get_absolute_url(self):
        return reverse("person_detail", args=[str(self.id)])


class Case(AuditedModel):
    case_num = models.PositiveIntegerField()
    applicant = models.ForeignKey(
        "Person", on_delete=models.CASCADE, null=True, blank=True
    )
    structure = models.ForeignKey(
        "Structure", on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"#{self.case_num} ({self.applicant})"

    def get_absolute_url(self):
        return reverse("case_detail", args=[str(self.id)])


class Structure(AuditedModel):
    location = models.CharField(max_length=256)

    def __str__(self):
        return str(self.location)

    def get_absolute_url(self):
        return reverse("structure_detail", args=[str(self.id)])


class CaseImporter(BaseAuditGroup):
    importee = models.OneToOneField(
        Case,
        related_name="importer",
        on_delete=models.CASCADE,
        # help_text="Reference to the audit group that 'holds' this audit",
    )

    @property
    def case(self):
        return self.importee


class CaseImportAttempt(BaseAudit):
    importer = models.OneToOneField(
        CaseImporter,
        related_name="attempts",
        on_delete=models.CASCADE,
        help_text="Reference to the audit group that 'holds' this audit",
    )
