from unittest import TestCase

from django.forms import CharField, Form

from . import FormMap, FieldMap
from .converters import handle_sectors, handle_location, handle_person, make_uppercase


class FooForm(Form):
    title = CharField()
    first_name = CharField()
    middle_name = CharField()
    last_name = CharField()
    sector_a = CharField()
    sector_b = CharField()
    sector_c = CharField()
    bar = CharField()
    flarm = CharField()
    location = CharField()


FooFormMap = FormMap(
    field_maps=[
        # n:n
        FieldMap(
            from_fields={"gender": ("gen",), "name": ("name", "n")},
            converter=handle_person,
            to_fields=("title", "first_name", "middle_name", "last_name"),
        ),
        # 1:n
        FieldMap(
            from_field="sectors",
            converter=handle_sectors,
            to_fields=("sector_a", "sector_b", "sector_c"),
        ),
        # n:1
        FieldMap(
            from_fields={"latitude": ("LAT", "lat"), "longitude": ("LONG", "long")},
            converter=handle_location,
            to_field="location",
        ),
        # 1:1, no converter
        FieldMap(from_field="foo", to_field="bar"),
        # 1:1, with converter
        FieldMap(from_field="flim", to_field="flarm", converter=make_uppercase),
    ],
    form_class=FooForm,
)


class FormMapTestCase(TestCase):
    def setUp(self):
        self.form_map = FooFormMap

    def test_complex(self):
        data = {
            "gender": "male",
            "name": "foo bar baz",
            "sectors": "a1 b2 c3",
            "foo": "blarg",
            "lat": "33",
            "long": "34",
            "unmapped": "doesn't matter",
            "flim": "abcd",
        }
        # with self.assertRaises(ValueError):
        #     # This should fail because we have an un-mapped header
        #     form_map.render_dict(data, allow_unprocessed=False)
        actual = self.form_map.render_dict(data)
        expected = {
            "title": "Mr.",
            "first_name": "foo",
            "middle_name": "bar",
            "last_name": "baz",
            "sector_a": "a1",
            "sector_b": "b2",
            "sector_c": "c3",
            "bar": "blarg",
            "flarm": "ABCD",
            "location": ("33", "34"),
        }
        self.assertEqual(actual, expected)

    def test_complex_with_missing_data(self):
        data = {
            "gender": "male",
            "name": "foo bar baz",
            "foo": "blarg",
            "lat": "33",
            "long": "34",
            "unmapped": "doesn't matter",
        }
        with self.assertRaises(ValueError):
            # This should fail because we have an un-mapped header
            self.form_map.render_dict(data, allow_unprocessed=False)
        actual = self.form_map.render_dict(data)
        expected = {
            "title": "Mr.",
            "first_name": "foo",
            "middle_name": "bar",
            "last_name": "baz",
            "bar": "blarg",
            "location": ("33", "34"),
        }
        self.assertEqual(actual, expected)

    def test_get_known_from_fields(self):
        actual = self.form_map.get_known_from_fields()
        expected = {
            "gender",
            "name",
            "sectors",
            "latitude",
            "longitude",
            "LAT",
            "lat",
            "LONG",
            "long",
            "foo",
            "flim",
            "n",
            "gen",
        }
        self.assertEqual(actual, expected)

    def test_unalias(self):
        headers = {"gender", "name", "foo", "lat", "long", "unmapped"}
        actual = self.form_map.unalias(headers)
        expected = {
            "gender": "gender",
            "name": "name",
            "latitude": "lat",
            "longitude": "long",
            "foo": "foo",
        }
        self.assertEqual(actual, expected)
