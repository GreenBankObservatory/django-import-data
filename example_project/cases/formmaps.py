from django_import_data import (
    FormMap,
    ManyToOneFieldMap,
    OneToManyFieldMap,
    OneToOneFieldMap,
    ManyToManyFieldMap,
)
from .forms import CaseForm, PersonForm, StructureForm


def coerce_positive_int(value):
    num = int(value)
    if num < 1:
        return None

    return num


class PersonFormMap(FormMap):
    form_class = PersonForm

    def convert_first_name_middle_name_last_name(
        self, first_name, middle_name, last_name
    ):
        print("convert_name!")
        return " ".join([first_name, middle_name, last_name])

    def convert_address(self, address):
        print("convert_address!")
        return dict(
            zip(
                ["street", "city", "state", "zip"],
                [p.strip() for p in address.split(",")],
            )
        )

    field_maps = [
        # n:1
        ManyToOneFieldMap(
            from_fields=("first_name", "middle_name", "last_name"),
            converter=lambda first_name, middle_name, last_name: " ".join(
                [first_name, middle_name, last_name]
            ),
            to_field="name",
        ),
        # 1:n
        OneToManyFieldMap(
            from_field={"address": ("address", "ADDR.")},
            to_fields=("street", "city", "state", "zip"),
        ),
        # 1:1
        OneToOneFieldMap(from_field="email", to_field="email"),
    ]


class CaseFormMap(FormMap):
    def convert_completed_type(self, completed, type):
        status = "complete" if completed else "incomplete"
        type_, subtype = type.split(" ")
        return {"status": status, "type": type_, "subtype": subtype}

    def convert_name(self, hmmm):
        pass

    form_class = CaseForm
    field_maps = [
        # 1:1
        OneToOneFieldMap(
            to_field="case_num", converter=coerce_positive_int, from_field="case_num"
        ),
        # n:n
        ManyToManyFieldMap(
            from_fields=("completed", "type"),
            # converter=convert_type,
            to_fields=("status", "type", "subtype"),
        ),
    ]


class StructureFormMap(FormMap):
    form_class = StructureForm
    field_maps = (
        ManyToOneFieldMap(
            from_fields=("latitude", "longitude"),
            to_field="location",
            converter="convert_location",
        ),
    )

    def convert_location(self, latitude, longitude):
        return {"location": (latitude, longitude)}
