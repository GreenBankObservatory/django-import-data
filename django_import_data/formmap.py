import itertools

from django.forms import ModelForm, ValidationError


class FormMap:
    """Simple mapping of ModelForm -> field-mapped data"""

    field_maps = [NotImplemented]
    form_class = NotImplemented
    form_defaults = {}

    def __init__(self, form_kwargs=None, check_every_render_for_errors=False):
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

    def render_dict(self, data, allow_unknown=True):
        rendered = {}

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
            rendered.update(field_map.render(data))

        return rendered

    def render(self, data, extra=None, allow_unknown=True):
        if not self.form_class:
            raise ValueError("No FormMap.form_class defined; cannot render a form!")
        if extra is None:
            extra = {}
        rendered = self.render_dict(data, allow_unknown)
        return self.form_class(
            {**self.form_defaults, **extra, **rendered}, **self.form_kwargs
        )

    def save(self, data, **kwargs):
        # Assume that if data is a ModelForm instance, it is an already-rendered
        # Form.
        if isinstance(data, ModelForm):
            form = data
        # Thus, if it is _not_ a ModelForm instance, we need to render it
        # ourselves
        else:
            form = self.render(data, **kwargs)

        if form.is_valid():
            return form.save()

        useful_errors = [
            {"field": field, "value": form[field].value(), "errors": errors}
            for field, errors in form.errors.as_data().items()
        ]

        raise ValidationError(
            f"{self.form_class.__name__} is invalid; couldn't be saved! {useful_errors}"
        )

    def get_known_from_fields(self):
        """Return set of all known from_fields, including aliases thereof"""

        known_fields = set()
        for field_map in self.field_maps:
            known_fields.update(field_map.known_fields)
        return known_fields

    def get_unknown_fields(self, data):
        return {field for field in data if field not in self.known_fields}

    def get_known_to_fields(self):
        return {
            to_field
            for field_map in self.field_maps
            for to_field in field_map.to_fields
        }

    def get_name(self):
        if self.form_class:
            model = self.form_class.Meta.model.__name__
            return f"FormMap<{model}>"

        return "FormMap"

    def __repr__(self):
        field_maps_str = "\n  ".join([str(field_map) for field_map in self.field_maps])
        return f"{self.get_name()} {{\n  {field_maps_str}\n}}"
