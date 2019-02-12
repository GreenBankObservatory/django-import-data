from collections import defaultdict
from pprint import pformat

from tqdm import tqdm

from django.forms import ModelForm, ValidationError

from .mermaid import render_form_map_as_mermaid

DEFAULT_THRESHOLD = 0.7


def get_useful_form_errors(form):
    return [
        {
            "field": field,
            "value": form[field].value(),
            "errors": [repr(error) for error in errors],
        }
        for field, errors in form.errors.as_data().items()
    ]


class FormMap:
    """Simple mapping of ModelForm -> field-mapped data"""

    field_maps = [NotImplemented]
    form_class = NotImplemented
    importer_class = NotImplemented
    form_defaults = {}

    def __init__(
        self,
        form_kwargs=None,
        check_every_render_for_errors=False,
        check_for_overloaded_to_fields=True,
    ):
        if form_kwargs:
            self.form_kwargs = form_kwargs
        else:
            self.form_kwargs = {}

        self.unaliased_map = None
        # self._rendered_form = None

        for field_map in self.field_maps:
            if not callable(field_map.converter):
                if field_map.converter:
                    converter_name = field_map.converter
                else:
                    converter_name = f"convert_{'_'.join(field_map.from_fields)}"
                try:
                    field_map.converter = getattr(self, converter_name)
                except AttributeError:
                    raise ValueError(
                        f"No {converter_name} found; either define one "
                        "or specify a different converter explicitly in "
                        "your FieldMap instantiation"
                    )

        self.known_fields = self.get_known_from_fields()
        # If this is set to True we will check every render call for
        # non-critical errors (such as unmapped fields). Otherwise we will check only the first
        self.check_every_render_for_errors = check_every_render_for_errors
        # Initialize this to True so that at least the first iteration
        # is checked. It might then be set to False depending on the above
        self.check_next_render_for_errors = True

        if check_for_overloaded_to_fields:
            overloaded_to_fields = self.get_overloaded_to_fields()
            if overloaded_to_fields:
                raise ValueError(
                    "The following to_fields are mapped to by multiple FieldMaps!\n"
                    f"{pformat(overloaded_to_fields)}"
                )

    def render_dict(self, data, allow_unknown=True):
        rendered = {}
        errors = []

        if self.check_next_render_for_errors:
            # Turn off error checking now unless user has specified
            # that we need to check every row
            if not self.check_every_render_for_errors:
                self.check_next_render_for_errors = False
            if not allow_unknown:
                unknown = self.get_unknown_fields(data)
                raise ValueError(f"Unknown fields: {unknown}")

        for field_map in self.field_maps:
            # NOTE: We do NOT pass allow_unknown to field_map. It
            # is essential to the functionality of our logic here
            # that it simply ignore all values it doesn't know about
            # Error checking is instead done above
            try:
                result = field_map.render(data)
            except ValueError as error:
                errors.append(
                    {
                        "error": repr(error),
                        "from_fields": field_map.from_fields,
                        "to_fields": field_map.to_fields,
                        "converter": field_map.converter.__name__,
                    }
                )
            else:
                if result:
                    rendered.update(result)

        return rendered, errors

    def render(
        self,
        data,
        extra=None,
        allow_unknown=True,
        allow_conversion_errors=True,
        allow_empty_forms=False,
    ):
        if not self.form_class:
            raise ValueError("No FormMap.form_class defined; cannot render a form!")
        if extra is None:
            extra = {}
        rendered, conversion_errors = self.render_dict(data, allow_unknown)
        if conversion_errors:
            if allow_conversion_errors:
                tqdm.write(f"Conversion errors: {pformat(conversion_errors)}")
            else:
                raise ValueError(f"One or more conversion errors: {conversion_errors}")

        if not allow_empty_forms and not any(rendered.values()):
            # tqdm.write(
            #     f"No values were derived for {self.form_class}; skipping creation attempt"
            # )
            rendered_form = None
        else:
            rendered_form = self.form_class(
                {**self.form_defaults, **extra, **rendered}, **self.form_kwargs
            )

        return (rendered_form, conversion_errors)

    # TODO: remove file_import_attempt; use row_data.file_import_attempt
    def save_with_audit(
        self,
        row_data,
        data=None,
        form=None,
        file_import_attempt=None,
        imported_by=None,
        **kwargs,
    ):
        from django.contrib.contenttypes.models import ContentType
        from django_import_data.models import ModelImportAttempt
        from .models import RowData

        if imported_by is None:
            raise ValueError("imported_by is required!")

        if not isinstance(row_data, RowData):
            raise ValueError("aw snap")

        # If no data has been explicitly given, use the whole row's data
        if data is None:
            data = row_data.data

        if form is not None:
            conversion_errors = {}
        else:
            # Thus, if it is _not_ a ModelForm instance, we need to render it
            # ourselves
            form, conversion_errors = self.render(data, **kwargs)
        if form is None:
            return (None, None)

        useful_form_errors = get_useful_form_errors(form)

        all_errors = {}
        if conversion_errors:
            all_errors["conversion_errors"] = conversion_errors
        if useful_form_errors:
            all_errors["form_errors"] = useful_form_errors
        if not (conversion_errors or useful_form_errors):
            model_import_attempt = ModelImportAttempt.objects.create_for_model(
                errors=all_errors,
                file_import_attempt=file_import_attempt,
                imported_by=imported_by,
                importee_field_data=form.data,
                model=form.Meta.model,
                row_data=row_data,
            )
            instance = form.save(commit=False)
            instance.model_import_attempt = model_import_attempt
            instance.save()
            return instance, model_import_attempt

        model_import_attempt = ModelImportAttempt.objects.create_for_model(
            errors=all_errors,
            file_import_attempt=file_import_attempt,
            imported_by=imported_by,
            importee_field_data=form.data,
            model=form.Meta.model,
            row_data=row_data,
        )
        return None, model_import_attempt

    # TODO: handle common functionality
    def save(self, data, **kwargs):
        if isinstance(data, ModelForm):
            # Assume that if data is a ModelForm instance, it is an already-rendered
            # Form. This also implies that there are no conversion errors
            form = data
            conversion_errors = {}
        else:
            # Thus, if it is _not_ a ModelForm instance, we need to render it
            # ourselves
            form, conversion_errors = self.render(data, **kwargs)

        if form.is_valid():
            instance = form.save()
            return instance

        useful_form_errors = get_useful_form_errors(form)
        all_errors = {
            "conversion_errors": conversion_errors,
            "form_errors": useful_form_errors,
        }

        raise ValidationError(
            f"{self.form_class.__name__} is invalid; couldn't be saved! {all_errors}"
        )

    def get_known_from_fields(self):
        """Return set of all known from_fields, including aliases thereof"""

        known_fields = set()
        for field_map in self.field_maps:
            known_fields.update(field_map.known_fields)
        return known_fields

    def get_unknown_fields(self, data):
        return {field for field in data if field not in self.known_fields}

    def get_known_to_fields(self, unique=True):
        if unique:
            return {
                to_field
                for field_map in self.field_maps
                for to_field in field_map.to_fields
            }
        return [
            to_field
            for field_map in self.field_maps
            for to_field in field_map.to_fields
        ]

    def get_name(self):
        if self.form_class and hasattr(self.form_class, "Meta"):
            model = self.form_class.Meta.model.__name__
            return f"FormMap<{model}>"

        return "FormMap"

    def explain(self):
        """EXPLAIN YOURSELF"""

        if not self.form_class:
            raise ValueError("There's nothing to explain!")

        form_fields = self.form_class().fields

        print(f"{self.__class__.__name__} maps:")

        for field_map in self.field_maps:
            from_fields_verbose, to_fields_verbose, explanation = field_map.explain(
                form_fields
            )
            print(f"  field(s):")
            for field_info in from_fields_verbose:
                print(f"    * {field_info}")

            print(f"  to field(s):")
            for field_info in to_fields_verbose:
                print(f"    * {field_info}")
            if field_map.converter.__name__ != "nop_converter":
                print(f"  via converter {field_map.converter.__name__}")

            if explanation:
                print(f"  explanation: {explanation}")
            print("-" * 3)

    def __repr__(self):
        field_maps_str = "\n  ".join([str(field_map) for field_map in self.field_maps])
        return f"{self.get_name()} {{\n  {field_maps_str}\n}}"

    def get_overloaded_to_fields(self, ignored=None):
        """Find instances where multiple FieldMaps map to the same to_field(s)"""

        if ignored is None:
            ignored = []

        to_field_to_containing_field_maps = defaultdict(list)
        for field_map in self.field_maps:
            for to_field in field_map.to_fields:
                to_field_to_containing_field_maps[to_field].append(field_map)

        return {
            to_field: field_maps
            for to_field, field_maps in to_field_to_containing_field_maps.items()
            if len(field_maps) > 1 and to_field not in ignored
        }

    def as_mermaid(self, *args, **kwargs):
        return render_form_map_as_mermaid(self, *args, **kwargs)
