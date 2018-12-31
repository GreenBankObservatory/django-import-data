from django.forms import ModelForm, ValidationError


class FormMap:
    """Simple mapping of ModelForm -> field-mapped data"""

    field_maps = NotImplemented
    form_class = NotImplemented
    form_defaults = {}

    def __init__(self, form_kwargs=None):
        if form_kwargs:
            self.form_kwargs = form_kwargs
        else:
            self.form_kwargs = {}

        self.unaliased_map = None
        # self._rendered_form = None

        for field_map in self.field_maps:
            if field_map.converter is None:
                converter_name = f"handle_{'_'.join(field_map.from_fields)}"
                try:
                    field_map.converter = getattr(self, converter_name)
                except AttributeError:
                    if field_map.map_type == field_map.ONE_TO_ONE:
                        field_map.converter = field_map.nop_converter
                    else:
                        import ipdb

                        ipdb.set_trace()
                        raise ValueError(
                            f"No {converter_name} found; either define one "
                            "or specify a different converter explicitly in "
                            "your FieldMap instantiation"
                        )

    def unalias(self, data):
        """Unalias!"""

        # TODO: Error checking. Shouldn't have more than one match per alias or something like that
        unaliased = {}
        for field_map in self.field_maps:
            for key in data:
                for from_field_alias, from_field_internal in field_map.aliases.items():
                    if key == from_field_alias:
                        unaliased[from_field_internal] = from_field_alias

        return unaliased

    def render_dict(self, data, allow_unprocessed=True, allow_missing=True):
        rendered = {}
        processed = set()

        if not self.unaliased_map:
            self.unaliased_map = self.unalias(data)

        for field_map in self.field_maps:
            from_field_data = {}

            for from_field in field_map.from_fields:
                # Either get the unaliased value of from_field, or, if one isn't
                # found, just use from_field itself
                data_key = self.unaliased_map.get(from_field, from_field)
                # print(f"data_key: {data_key}")
                try:
                    from_field_data[data_key] = data[data_key]
                except KeyError as error:
                    if not allow_missing:
                        raise error
                    else:
                        # print(
                        # f"WARNING: Expected key {data_key!r} is missing "
                        # f"from data: {data.keys()}"
                        # )
                        pass

            rendered.update(field_map.map(from_field_data))
            processed.update(from_field_data.keys())

        # print("processed")
        # pprint(processed)

        unprocessed = set(data.keys()).difference(processed)
        if unprocessed:
            message = f"Did not process the following data fields: {unprocessed}"
            if not allow_unprocessed:
                raise ValueError(message)
            # print(f"WARNING: {message}")

        return rendered

    def render(self, data, extra=None, allow_unprocessed=True, allow_missing=True):
        if not self.form_class:
            raise ValueError("No FormMap.form_class defined; cannot render a form!")
        if extra is None:
            extra = {}
        rendered = self.render_dict(data, allow_unprocessed, allow_missing)
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

        return {
            from_field
            for field_map in self.field_maps
            for from_field in list(field_map.aliases.keys()) + field_map.from_fields
        }

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
