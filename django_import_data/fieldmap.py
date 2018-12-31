"""Provides utilities for mapping header->field

The problem: we have a bunch of Excel files, e.g., that have columnar data we
wish to create model instances from. Each column should map to a field, but
the columns don't always have the same names between Excel files. So, we need
some way to map all possible column headers to their appropriate field.

Additionally, we need a way to link a "converter" to each pairing -- this is
responsible for cleaning the data and converting it to the proper type. For
example, if we have a boolean column that represents None as either "" or "n/a",
depending on the file, we need a way to say that all of those mean the same thing.

This module contains all of the converters and the FieldMap class itself,
as well as an dictionary of every known header to its mapped field -- "expanded"
from the list of FieldMap instances
"""


class FieldMap:
    """Map a to_field to its associated from_fields, a converter function, and any aliases"""

    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:*"
    MANY_TO_ONE = "*:1"
    MANY_TO_MANY = "*:*"

    map_type = NotImplemented

    def __init__(
        self,
        to_fields=None,
        converter=None,
        from_fields=None,
        # aliases=None,
    ):
        if isinstance(to_fields, str) or isinstance(from_fields, str):
            raise ValueError("to_fields and from_fields should not be strings!")

        self.to_fields = to_fields
        self.from_fields = from_fields
        # Function to convert/clean data
        self.converter = converter

        if isinstance(self.from_fields, dict):
            self.aliases = {key: value for key, value in self.from_fields.items()}
            self.aliases.update(self._invert_aliases(self.from_fields))
            self.from_fields = list(self.from_fields.keys())
        else:
            # If no aliases exist, create them
            self.aliases = {from_field: from_field for from_field in self.from_fields}

    def nop_converter(self, value):
        """Perform no conversion; simply return value"""
        return value

    @staticmethod
    def _invert_aliases(fields_to_aliases):
        """Given dict of {field: aliases}, return dict of {alias: field}

        For example, if fields_to_aliases={
            "latitude": ("LAT", "lat."), "longitude": ("LONG", "long.")
        }, then we return:
        {
            'LAT': 'latitude',
            'lat.': 'latitude',
            'LONG': 'longitude',
            'long.': 'longitude'
        }
        """
        return {
            alias: field
            for field, aliases in fields_to_aliases.items()
            for alias in aliases
        }

    def __repr__(self):
        if len(self.from_fields) == 1:
            from_ = "1"
            try:
                from_fields = self.from_fields[0]
            except KeyError:
                from_fields = next(iter(self.from_fields.keys()))
        else:
            from_ = "*"
            from_fields = self.from_fields

        if len(self.to_fields) == 1:
            to = "1"
            to_fields = self.to_fields[0]
        else:
            to = "*"
            to_fields = self.to_fields
        if callable(self.converter):
            converter = self.converter.__name__
        else:
            converter = self.converter

        return f"FieldMap: {from_fields!r} [{from_}]—({converter})—[{to}] {to_fields!r}"
        # return f"FieldMap: {self.converter.__name__}({from_fields!r}) -> {to_fields!r}"

    def check_unmapped_from_fields(self):
        if self.aliases:
            unmapped_from_fields = [key for key in data if key not in self.aliases]
            if unmapped_from_fields:
                raise ValueError(
                    f"Found fields {unmapped_from_fields} with no known alias. "
                    f"Known aliases: {self.aliases}"
                )

    def map(self, data):
        ret = {self.aliases.get(key, key): value for key, value in data.items()}
        # print("ret", ret)
        if not ret:
            # print(f"WARNING: Failed to produce value for {data}")
            return {}

        # Handle the simple 1:1/n:1 cases here to save on boilerplate externally
        # That is, allow for the existence of converters that don't return
        # {to_field: converted values} dicts, and instead simply return
        # converted values
        if self.map_type in (self.ONE_TO_ONE, self.MANY_TO_ONE):
            to_field = self.to_fields[0]
            if self.map_type == self.MANY_TO_ONE:
                converted = self.converter(**ret)
                if not isinstance(converted, dict):
                    return {to_field: converted}
                return converted

            from_field_value = next(iter(ret.values()))
            return {to_field: self.converter(from_field_value)}

        # For all other cases, expect the converter to be smart enough
        return self.converter(**ret)


class OneToOneFieldMap(FieldMap):
    map_type = FieldMap.ONE_TO_ONE

    def __init__(self, from_field, to_field=None, converter=None):
        if to_field is None:
            to_field = from_field

        if isinstance(from_field, dict):
            from_fields = from_field
        else:
            from_fields = [from_field]
        super().__init__(
            from_fields=from_fields, to_fields=[to_field], converter=converter
        )

    def map(self, data):
        ret = {self.aliases.get(key, key): value for key, value in data.items()}
        # Handle case where we don't have any mappings
        if not ret:
            return {}
        # Handle the simple 1:1/n:1 cases here to save on boilerplate externally
        # That is, allow for the existence of converters that don't return
        # {to_field: converted values} dicts, and instead simply return
        # converted values
        to_field = self.to_fields[0]
        from_field_value = next(iter(ret.values()))
        return {to_field: self.converter(from_field_value)}


class ManyToOneFieldMap(FieldMap):
    map_type = FieldMap.MANY_TO_ONE

    def __init__(self, from_fields, to_field, converter=None):
        super().__init__(
            from_fields=from_fields, to_fields=[to_field], converter=converter
        )

    def map(self, data):
        ret = {self.aliases.get(key, key): value for key, value in data.items()}
        # Allow for the existence of converters that don't return
        # {to_field: converted values} dicts, and instead simply return
        # converted values
        to_field = self.to_fields[0]
        converted = self.converter(**ret)
        if not isinstance(converted, dict):
            return {to_field: converted}
        return converted


class OneToManyFieldMap(FieldMap):
    map_type = FieldMap.ONE_TO_MANY

    def __init__(self, from_field, to_fields, converter=None):
        if isinstance(from_field, dict):
            from_fields = from_field
        else:
            from_fields = [from_field]
        super().__init__(
            from_fields=from_fields, to_fields=to_fields, converter=converter
        )


class ManyToManyFieldMap(FieldMap):
    map_type = FieldMap.MANY_TO_MANY
