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
DEFAULT_CONVERTER = None
DEFAULT_ALLOW_UNKNOWN = True
DEFAULT_ALLOW_MULTIPLE_ALIASES_FOR_FIELD = False

from collections import defaultdict
from inspect import getfullargspec

from .mermaid import render_field_map_as_mermaid
from .utils import to_fancy_str


class FieldMap:
    """Map a to_field to its associated from_fields, a converter function, and any aliases"""

    # TODO: Distribute these to child classes
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:*"
    MANY_TO_ONE = "*:1"
    MANY_TO_MANY = "*:*"

    map_type = NotImplemented

    def __init__(
        self,
        from_fields,
        to_fields,
        converter=DEFAULT_CONVERTER,
        aliases=None,
        explanation=None,
    ):
        # Strings are iterable, so will "work" for a large portion of the
        # processing, but aren't ever actually correct. So, just catch this
        # common error here and fail loudly up front
        if isinstance(to_fields, str) or isinstance(from_fields, str):
            raise TypeError("to_fields and from_fields should not be strings!")

        self.to_fields = to_fields
        self.from_fields = from_fields
        # Function to convert/clean data. Only set if it is actually given!
        # This allows child classes to make their own decisions regarding it
        # if converter is not None:
        self.converter = converter

        from_fields_is_compound = isinstance(from_fields, dict)

        if aliases and from_fields_is_compound:
            raise ValueError(
                "If aliases is given, from_fields cannot be "
                "a compound from_fields/aliases dict"
            )

        if aliases is not None:
            self.fields_to_aliases = aliases
        # Aliases are given via dict, so handle this case
        if isinstance(from_fields, dict):
            self.aliases, self.fields_to_aliases, self.from_fields = self._split_from_fields(
                from_fields
            )
        else:
            self.aliases = {}
            self.fields_to_aliases = {}

        # if converter is None:
        #     raise ValueError("converter must be given!")
        # if not callable(converter):
        #     raise ValueError("converter must be a callable!")

        # This is a set of all possible mappable fields. That is, we can
        # map a field directly (where no alias is defined), or we can map
        # any of its aliases.
        self.known_fields = set([*self.from_fields, *self.aliases])

        if not self.map_type:
            raise ValueError(
                "map_type must be set! Typically this is done by a sub-class"
            )

        self.explanation = explanation

    @classmethod
    def _expand_aliases(cls, fields_to_aliases):
        expanded = {}
        for field, aliases in fields_to_aliases.items():
            if aliases is not None:
                if isinstance(aliases, str):
                    alias = aliases
                    expanded[field] = [alias]
                else:
                    expanded[field] = aliases

        return expanded

    @property
    def converter_name(self):
        return self.converter.__name__ if self.converter else "<no converter>"

    def has_converter(self):
        if not self.converter:
            return False

        if self.converter.__name__ == "nop_converter":
            return False

        return True

    @classmethod
    def _split_from_fields(cls, from_fields):
        if not isinstance(from_fields, dict):
            raise ValueError(
                "_split_from_fields requires aliases to be passed "
                "in as a dict of {from_field: aliases}"
            )
        inverted_aliases = cls._invert_aliases(from_fields)
        expanded_aliases = cls._expand_aliases(from_fields)
        from_fields = tuple(from_fields.keys())
        return inverted_aliases, expanded_aliases, from_fields

    @classmethod
    def _invert_aliases(cls, fields_to_aliases):
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
        inverted = {}
        for field, aliases in fields_to_aliases.items():
            if aliases is not None:
                if isinstance(aliases, str):
                    alias = aliases
                    inverted[alias] = field
                else:
                    for alias in aliases:
                        inverted[alias] = field
        return inverted

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(\n"
            f"  from_fields={self.from_fields!r},\n"
            f"  converter={self.converter.__name__},\n"
            f"  to_fields={self.to_fields!r}\n,"
            f"  aliases={self.aliases!r}\n,"
            ")"
        )

    def __str__(self):
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

    def get_unknown_fields(self, data):
        return {field for field in data if field not in self.known_fields}

    def get_from_fields_without_aliases(self):
        if self.fields_to_aliases:
            return [
                from_field
                for from_field in self.from_fields
                if from_field not in self.fields_to_aliases
            ]
        return self.from_fields

    def unalias(
        self,
        data,
        allow_unknown=DEFAULT_ALLOW_UNKNOWN,
        allow_multiple_aliases_for_field=DEFAULT_ALLOW_MULTIPLE_ALIASES_FOR_FIELD,
    ):
        unaliased_data = {}
        found_aliases = defaultdict(list)
        for alias, value in data.items():
            if alias in self.known_fields:
                # Get the unaliased alias, or, if there's no alias, just
                # use the alias name as is
                unaliased_field = self.aliases.get(alias, alias)
                found_aliases[unaliased_field].append(alias)
                unaliased_data[unaliased_field] = value
            else:
                if not allow_unknown:
                    raise ValueError(
                        f"Field {alias} is not a known field "
                        f"({self.known_fields})! To suppress this error, "
                        "pass allow_unknown=True"
                    )
        if not allow_multiple_aliases_for_field:
            found_aliases = dict(found_aliases)
            duplicated_aliases = {
                field: aliases
                for field, aliases in found_aliases.items()
                if len(aliases) > 1
            }
            if duplicated_aliases:
                raise TypeError(
                    f"More than one alias found in the data: {duplicated_aliases}. "
                    "This indicates that you probably need to split this FieldMap in two..."
                )
        return unaliased_data

    # TODO: This has no place here... this should _perhaps_ perform
    # core functionality, but most rendering should now be distributed
    # to child classes
    def render(
        self,
        data,
        converter=DEFAULT_CONVERTER,
        allow_unknown=DEFAULT_ALLOW_UNKNOWN,
        allow_multiple_aliases_for_field=DEFAULT_ALLOW_MULTIPLE_ALIASES_FOR_FIELD,
    ):
        if converter is None:
            converter = self.converter
        ret = self.unalias(
            data,
            allow_unknown=allow_unknown,
            allow_multiple_aliases_for_field=allow_multiple_aliases_for_field,
        )
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
                try:
                    converted = converter(**ret)
                except TypeError as error:
                    if "argument" in str(error):
                        argspec = getfullargspec(converter)
                        raise TypeError(
                            f"Converter {converter.__name__} (args: {argspec.args}) rejected args: {list(ret)}"
                        ) from error
                if not isinstance(converted, dict):
                    return {to_field: converted}
                return converted

            from_field_value = next(iter(ret.values()))
            return {to_field: converter(from_field_value)}

        # For all other cases, expect the converter to be smart enough
        try:
            return converter(**ret)
        except TypeError as error:
            argspec = getfullargspec(converter)
            raise TypeError(
                f"Converter {converter.__name__} ({argspec.args}) rejected args: {list(ret)}"
            ) from error

    def _explain_from_fields(self, form_fields, field_names):
        fields_verbose = []
        for field_name in field_names:
            try:
                field = form_fields[field_name]
            except KeyError as error:
                # raise ValueError(
                #     f"Invalid FormMap! {field_name} does not exist in form class {self.form_class}"
                # ) from error
                fields_verbose.append(field_name)
            else:
                help_text = field.help_text
                name_str = field_name
                if field.label:
                    name_str += f" ({repr(field.label)})"
                if help_text:
                    name_str += f" ({help_text})"
                fields_verbose.append(name_str)
        return tuple(fields_verbose)

    def _explain_to_fields(self, form_fields, field_names):
        fields_verbose = []
        for field_name in field_names:
            try:
                field = form_fields[field_name]
            except KeyError as error:
                # raise ValueError(
                #     f"Invalid FormMap! {field_name} does not exist in form class {self.form_class}"
                # ) from error
                fields_verbose.append(field_name)
            else:
                if self.aliases:
                    inverted = tuple(
                        [
                            alias
                            for alias, field in self.aliases.items()
                            if field == field_name
                        ]
                    )
                    if inverted:
                        name_str = f"{field_name}, under aliases:"
                        for alias in inverted:
                            name_str += f"\n      * {alias}"
                    else:
                        name_str = field_name
                else:
                    name_str = field_name
                fields_verbose.append(name_str)
        return tuple(fields_verbose)

    def explain(self, form_fields):
        d = {}
        from_fields_verbose = self._explain_to_fields(form_fields, self.from_fields)
        to_fields_verbose = self._explain_from_fields(form_fields, self.to_fields)

        return from_fields_verbose, to_fields_verbose, self.explanation
        # print(f"from_fields_verbose: {from_fields_verbose}")
        # print(f"to_fields_verbose: {to_fields_verbose}")

    def as_mermaid(self, *args, **kwargs):
        return render_field_map_as_mermaid(self, *args, **kwargs)

    def as_sentence(self):
        from_fields_label = "fields" if len(self.from_fields) > 1 else "field"
        to_fields_label = "fields" if len(self.to_fields) > 1 else "field"
        return (
            f"Maps {from_fields_label} {to_fancy_str(self.from_fields, quote=True)} "
            f"to {to_fields_label} {to_fancy_str(self.to_fields, quote=True)} "
            f"via converter {self.converter_name!r}"
        )

    def get_name(self):
        return self.__class__.__name__


class OneToOneFieldMap(FieldMap):
    map_type = FieldMap.ONE_TO_ONE

    def __init__(
        self, from_field, to_field=None, converter=DEFAULT_CONVERTER, explanation=None
    ):
        # If from_field is a dict then it contains a single field along with its aliases
        if isinstance(from_field, dict):
            if len(from_field) != 1:
                raise ValueError(
                    "If from_field is given as a dict, "
                    "it must contain only one member!"
                )
            # This means that it can be directly set as our from_fields
            from_fields = from_field
            # But we need to pull out its key (the field designation) to
            # populate our to_field
            if to_field is None:
                to_field = next(iter(from_field))
        else:
            # If it isn't a dict, assume that it is some sort of sensible
            # atomic value and put it in a list
            from_fields = [from_field]
            # If to_field still wasn't set, just set it
            # directly from from_field
            if to_field is None:
                to_field = from_field

        # TODO: Shouldn't this conflict with the convert_foo logic in formmap init?
        if converter is None:
            converter = self.nop_converter
        super().__init__(
            from_fields=from_fields,
            to_fields=[to_field],
            converter=converter,
            explanation=explanation,
        )
        assert len(self.from_fields) == 1, "Should only be one from field!"
        self.from_field = self.from_fields[0]
        assert len(self.to_fields) == 1, "Should only be one to field!"
        self.to_field = self.to_fields[0]

    # TODO: Consider having this return a dict?
    def nop_converter(self, value):
        """Perform no conversion; simply return value"""
        return value

    def render(
        self,
        data,
        converter=DEFAULT_CONVERTER,
        allow_unknown=DEFAULT_ALLOW_UNKNOWN,
        allow_multiple_aliases_for_field=DEFAULT_ALLOW_MULTIPLE_ALIASES_FOR_FIELD,
    ):
        if converter is None:
            converter = self.converter
        ret = self.unalias(
            data,
            allow_unknown=allow_unknown,
            allow_multiple_aliases_for_field=allow_multiple_aliases_for_field,
        )
        # Handle case where we don't have any mappings (need to bail early
        # to avoid breaking logic below)
        if not ret:
            return {}
        # Handle the simple 1:1/n:1 cases here to save on boilerplate externally
        # That is, allow for the existence of converters that don't return
        # {to_field: converted values} dicts, and instead simply return
        # converted values
        to_field = self.to_fields[0]
        from_field_value = next(iter(ret.values()))
        try:
            converted = converter(from_field_value)
        except TypeError as error:
            raise  # ValueError("Unmapped headers!") from error
        if not isinstance(converted, dict):
            return {to_field: converted}
        return converted


class ManyToOneFieldMap(FieldMap):
    map_type = FieldMap.MANY_TO_ONE

    def __init__(
        self, from_fields, to_field, converter=DEFAULT_CONVERTER, explanation=None
    ):
        super().__init__(
            from_fields=from_fields,
            to_fields=[to_field],
            converter=converter,
            explanation=explanation,
        )
        assert len(self.to_fields) == 1, "Should only be one to field!"
        self.to_field = self.to_fields[0]

    def render(
        self,
        data,
        converter=DEFAULT_CONVERTER,
        allow_unknown=DEFAULT_ALLOW_UNKNOWN,
        allow_multiple_aliases_for_field=DEFAULT_ALLOW_MULTIPLE_ALIASES_FOR_FIELD,
    ):
        if converter is None:
            converter = self.converter
        ret = self.unalias(
            data,
            allow_unknown=allow_unknown,
            allow_multiple_aliases_for_field=allow_multiple_aliases_for_field,
        )
        # Allow for the existence of converters that don't return
        # {to_field: converted values} dicts, and instead simply return
        # converted values
        to_field = self.to_fields[0]
        try:
            converted = converter(**ret)
        except TypeError as error:
            if "argument" in str(error):
                argspec = getfullargspec(converter)
                raise TypeError(
                    f"Converter {converter.__name__} ({argspec.args}) rejected args: {list(ret)}"
                ) from error

        if not isinstance(converted, dict):
            return {to_field: converted}
        return converted


class OneToManyFieldMap(FieldMap):
    map_type = FieldMap.ONE_TO_MANY

    def __init__(
        self, from_field, to_fields, converter=DEFAULT_CONVERTER, explanation=None
    ):
        if isinstance(from_field, dict):
            from_fields = from_field
        else:
            from_fields = [from_field]
        super().__init__(
            from_fields=from_fields,
            to_fields=to_fields,
            converter=converter,
            explanation=explanation,
        )
        assert len(self.from_fields) == 1, "Should only be one from field!"
        self.from_field = self.from_fields[0]


class ManyToManyFieldMap(FieldMap):
    map_type = FieldMap.MANY_TO_MANY
