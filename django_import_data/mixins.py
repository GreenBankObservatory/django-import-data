from django.db import models

from .utils import OrderedEnum


class ImportStatusModel(models.Model):
    class STATUSES(OrderedEnum):
        # NOTE: Order here matters; it is used to determine precedence
        pending = "Pending"
        created_clean = "Imported: No Errors"
        created_dirty = "Imported: Some Errors"
        rejected = "Rejected: Fatal Errors"

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


class IsActiveModel(models.Model):
    """An abstract class that allows objects to be 'soft' deleted.
    """

    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
