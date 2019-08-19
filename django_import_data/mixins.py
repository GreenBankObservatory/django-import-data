import os
from datetime import datetime

from django.db import models
from django.utils.timezone import make_aware, now

from .utils import OrderedEnum, hash_file


class SensibleTextyField:
    def __init__(self, *args, **kwargs):
        null_given = "null" in kwargs
        null = kwargs.get("null", False)
        blank = kwargs.get("blank", False)
        unique = kwargs.get("unique", False)
        # (kwargs.get("default", models.NOT_PROVIDED),)

        if not (unique is True and blank is True) and null is True:
            raise ValueError(
                f"{self.__class__.__name__} doesn't allow null=True unless unique=True AND blank=True! "
                "See https://docs.djangoproject.com/en/2.1/ref/models/fields/#null for more details"
            )

        if unique is True and blank is True:
            if null_given and null is False:
                raise ValueError(
                    f"{self.__class__.__name__} doesn't allow null=False if unique=True AND blank=True! "
                    "See https://docs.djangoproject.com/en/2.1/ref/models/fields/#null for more details"
                )
            kwargs["null"] = True

        if blank is False and null is False:
            kwargs["default"] = None

        super().__init__(*args, **kwargs)


class SensibleCharField(SensibleTextyField, models.CharField):
    pass


class SensibleTextField(SensibleTextyField, models.TextField):
    pass


class SensibleEmailField(SensibleTextyField, models.EmailField):
    pass


class CurrentStatusModel(models.Model):
    class CURRENT_STATUSES(OrderedEnum):
        # NOTE: Order here matters; it is used to determine precedence
        deleted = "Deleted"
        acknowledged = "Acknowledged"
        active = "Active"

    current_status = models.PositiveIntegerField(
        choices=CURRENT_STATUSES.as_choices(),
        default=CURRENT_STATUSES.active.db_value,
        db_index=True,
    )

    def is_acknowledged(self):
        return self.current_status == self.CURRENT_STATUSES.acknowledged.db_value

    def is_active(self):
        return self.current_status == self.CURRENT_STATUSES.active.db_value

    def is_deleted(self):
        return self.current_status == self.CURRENT_STATUSES.deleted.db_value

    class Meta:
        abstract = True


class ImportStatusModel(models.Model):
    class STATUSES(OrderedEnum):
        # NOTE: Order here matters; it is used to determine precedence
        pending = "Pending"
        created_clean = "Complete Success"
        empty = "Empty"
        created_dirty = "Partial Success"
        rejected = "Failure"

    status = models.PositiveIntegerField(
        choices=STATUSES.as_choices(), default=STATUSES.pending.db_value, db_index=True
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


class TrackedFileMixin(models.Model):
    file_path = SensibleCharField(
        max_length=512, help_text="Path to the file that this is linked to", unique=True
    )
    hash_on_disk = SensibleCharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text="SHA-1 hash of the file on disk. If blank, the file is missing",
    )
    file_modified_on = models.DateTimeField(null=True, blank=True)
    hash_checked_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def file_missing(self):
        return not self.hash_on_disk

    @property
    def file_changed(self):
        return self.refresh_from_filesystem() == "changed"

    def refresh_from_filesystem(self, always_hash=False):
        try:
            # If the file can be found, we determine its modification time
            # This is done regardless of whether the files contents have changed
            fs_file_modified_on = make_aware(
                datetime.fromtimestamp(os.path.getmtime(self.file_path))
            )
        except FileNotFoundError:
            # If the file can't be found, we set the hash to None,
            # and the status to missing
            self.hash_on_disk = None
            status = "missing"
        else:
            if self.file_modified_on != fs_file_modified_on or always_hash:
                self.file_modified_on = fs_file_modified_on
                self.hash_checked_on = now()
                # Attempt to determine the hash of the file on disk
                actual_hash_on_disk = hash_file(self.file_path)
                # Now determine whether the contents of the file have changed since
                # last check
                if self.hash_on_disk != actual_hash_on_disk:
                    # If the file has changed, update its hash in the instance
                    self.hash_on_disk = actual_hash_on_disk
                    status = "changed"
                else:
                    status = "unchanged"
            else:
                status = "skipped"

            self.save()
        return status
