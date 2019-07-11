import logging

from django_import_data import BaseImportCommand

from importers.example_data_source.form_maps import (
    CASE_FORM_MAP,
    PERSON_FORM_MAP,
    STRUCTURE_FORM_MAP,
)

LOGGER = logging.getLogger(__name__)
print("__name__", __name__)


class Command(BaseImportCommand):
    PROGRESS_TYPE = BaseImportCommand.PROGRESS_TYPES.ROW
    FORM_MAPS = [CASE_FORM_MAP, PERSON_FORM_MAP, STRUCTURE_FORM_MAP]

    # IGNORED_HEADERS = IGNORED_HEADERS

    def handle_record(self, row_data, durable=True):
        LOGGER.debug(f"Handling row: {row_data.data}")
        applicant, applicant_audit = PERSON_FORM_MAP.save_with_audit(
            row_data=row_data, imported_by=self.__module__
        )
        structure, structure_audit = STRUCTURE_FORM_MAP.save_with_audit(
            row_data=row_data, imported_by=self.__module__
        )

        case, case_audit = CASE_FORM_MAP.save_with_audit(
            row_data=row_data,
            imported_by=self.__module__,
            extra={
                "applicant": applicant.id if applicant else None,
                "structure": structure.id if structure else None,
            },
        )
