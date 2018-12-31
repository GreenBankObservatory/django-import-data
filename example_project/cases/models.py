from django.db import models


class Person(models.Model):
    name = models.CharField(max_length=256, blank=True)
    phone = models.CharField(max_length=256, blank=True)
    email = models.EmailField(null=True, blank=True)


class Attachment(models.Model):
    path = models.CharField(max_length=256, unique=True)


class Case(models.Model):
    applicant = models.ForeignKey("Person", on_delete=models.CASCADE)
    attachments = models.ManyToManyField("Attachment", related_name="cases", blank=True)
    group = models.ForeignKey(
        "CaseGroup", on_delete=models.CASCADE, related_name="cases"
    )


class CaseGroup(models.Model):
    name = models.CharField(max_length=256, blank=True)
