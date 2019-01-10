from enum import Enum

from django.db import models


class ImportStatusModel(models.Model):
    class STATUSES(Enum):
        rejected = "Rejected: Fatal Errors"
        created_dirty = "Imported: Some Errors"
        created_clean = "Imported: No Errors"
        pending = "Pending"

        @classmethod
        def get_default(cls):
            """Get the default choice value"""
            return cls.pending.name

    status = models.CharField(
        max_length=max([len(s.name) for s in STATUSES]),
        choices=((status.name, status.value) for status in STATUSES),
        default=STATUSES.get_default(),
    )

    class Meta:
        abstract = True


class TrackedModel(models.Model):
    """An abstract class for any models that need to track who
    created or last modified an object and when.
    """

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True
