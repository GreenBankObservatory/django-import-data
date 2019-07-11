from django.db import models
from django.urls import reverse

from django_import_data.models import (
    AbstractBaseAuditedModel,
    AbstractBaseModelImportAttempt,
)


class Person(AbstractBaseAuditedModel):
    name = models.CharField(max_length=256, blank=True)
    phone = models.CharField(max_length=256, blank=True)
    email = models.EmailField(null=True, blank=True)
    city = models.CharField(max_length=256, blank=True)
    street = models.CharField(max_length=256, blank=True)
    zip = models.CharField(max_length=256, blank=True)
    state = models.CharField(max_length=256, blank=True)

    def __str__(self):
        return f"{self.name}; {self.phone}; {self.email}"

    def get_absolute_url(self):
        return reverse("person_detail", args=[str(self.id)])


class Case(AbstractBaseAuditedModel):
    case_num = models.PositiveIntegerField()
    applicant = models.ForeignKey(
        "Person", on_delete=models.CASCADE, null=True, blank=True
    )
    structure = models.ForeignKey(
        "Structure", on_delete=models.CASCADE, null=True, blank=True
    )
    status = models.CharField(
        choices=(("incomplete", "incomplete"), ("complete", "complete")), max_length=256
    )
    type = models.CharField(max_length=256, blank=True)
    subtype = models.PositiveIntegerField(blank=True)

    def __str__(self):
        return f"#{self.case_num} ({self.applicant})"

    def get_absolute_url(self):
        return reverse("case_detail", args=[str(self.id)])


class Structure(AbstractBaseAuditedModel):
    location = models.CharField(max_length=256)

    def __str__(self):
        return str(self.location)

    def get_absolute_url(self):
        return reverse("structure_detail", args=[str(self.id)])
