from django.db import models


class Person(models.Model):
    name = models.CharField(max_length=256, blank=True)
    phone = models.CharField(max_length=256, blank=True)
    email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}; {self.phone}; {self.email}"


class Case(models.Model):
    case_num = models.PositiveIntegerField()
    applicant = models.ForeignKey(
        "Person", on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"#{self.case_num} ({self.applicant})"


class Structure(models.Model):
    location = models.CharField(max_length=256)

    def __str__(self):
        return str(self.location)
