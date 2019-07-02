from django.db import models

from .utils import OrderedEnum


class ImportStatusModel(models.Model):
    class STATUSES(OrderedEnum):
        # NOTE: Order here matters; it is used to determine precedence
        pending = "Pending"
        empty = "Empty"
        deleted = "Deleted"
        created_clean = "Complete Success"
        created_dirty = "Partial Success"
        rejected = "Failure"

        @classmethod
        def get_default(cls):
            """Get the default choice value"""
            return cls.pending.name

    status = models.PositiveIntegerField(
        choices=STATUSES.as_choices(), default=0, db_index=True
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

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True
