from unittest import TestCase

from django.forms import CharField, Form
from . import (
    FormMap,
    FieldMap,
    ManyToManyFieldMap,
    OneToManyFieldMap,
    ManyToOneFieldMap,
    OneToOneFieldMap,
)
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


class FooFormMap(FormMap):
    field_maps = [
        # n:n
        ManyToManyFieldMap(
            from_fields={"gender": ("gen",), "name": ("name", "n")},
            converter=handle_person,
            to_fields=("title", "first_name", "middle_name", "last_name"),
        ),
        # 1:n
        OneToManyFieldMap(
            from_field="sectors",
            converter=handle_sectors,
            to_fields=("sector_a", "sector_b", "sector_c"),
        ),
        # n:1
        ManyToOneFieldMap(
            from_fields={"latitude": ("LAT", "lat"), "longitude": ("LONG", "long")},
            converter=handle_location,
            to_field="location",
        ),
        # 1:1, no converter
        OneToOneFieldMap(from_field="foo", to_field="bar"),
        # 1:1, with converter
        OneToOneFieldMap(from_field="flim", to_field="flarm", converter=make_uppercase),
    ]
    form_class = FooForm


class FormMapTestCase(TestCase):
    def setUp(self):
        self.form_map = FooFormMap()

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
            "unmapped1": "doesn't matter",
            "unmapped2": "doesn't matter",
        }
        # Error message should include names of unmapped headers as a set
        with self.assertRaisesRegex(ValueError, str({"unmapped1", "unmapped2"})):
            # This should fail because we have un-mapped headers
            self.form_map.render_dict(data, allow_unknown=False)
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

    def test_get_unknown_fields(self):
        data = {"flamingo": "bar", "pidgeon": "bin"}
        actual = self.form_map.get_unknown_fields(data)
        expected = {"flamingo", "pidgeon"}
        self.assertEqual(actual, expected)

    def test_check_first_render_for_errors(self):
        data = {
            "gender": "male",
            "name": "foo bar baz",
            "foo": "blarg",
            "lat": "33",
            "long": "34",
            "unmapped1": "doesn't matter",
            "unmapped2": "doesn't matter",
        }

        # Our form_map should be set to check the next render for errors
        self.assertTrue(self.form_map.check_next_render_for_errors)
        # But it should be set to check only the first (i.e. not every one)
        self.assertFalse(self.form_map.check_every_render_for_errors)
        # Error message should include names of unmapped headers as a set
        with self.assertRaisesRegex(ValueError, str({"unmapped1", "unmapped2"})):
            # This should fail because we have un-mapped headers
            self.form_map.render_dict(data, allow_unknown=False)

        # Our form_map should now be set to NOT check the next render for errors
        self.assertFalse(self.form_map.check_next_render_for_errors)
        # And should still be set to check only the first
        self.assertFalse(self.form_map.check_every_render_for_errors)
        self.form_map.render_dict(data, allow_unknown=False)

    def test_check_every_render_for_errors(self):
        data = {
            "gender": "male",
            "name": "foo bar baz",
            "foo": "blarg",
            "lat": "33",
            "long": "34",
            "unmapped1": "doesn't matter",
            "unmapped2": "doesn't matter",
        }

        # Set this to true; we want to check every render
        self.form_map.check_every_render_for_errors = True

        # Our form_map should be set to check the next render for errors
        self.assertTrue(self.form_map.check_next_render_for_errors)
        # But it should be set to check only the first (i.e. not every one)
        self.assertTrue(self.form_map.check_every_render_for_errors)
        # Error message should include names of unmapped headers as a set
        with self.assertRaisesRegex(ValueError, str({"unmapped1", "unmapped2"})):
            # This should fail because we have un-mapped headers
            self.form_map.render_dict(data, allow_unknown=False)

        # Our form_map should be STILL set to check the next render for errors
        self.assertTrue(self.form_map.check_next_render_for_errors)
        # And it should STILL be set to check only the first (i.e. not every one)
        self.assertTrue(self.form_map.check_every_render_for_errors)
        # Error message should include names of unmapped headers as a set
        with self.assertRaisesRegex(ValueError, str({"unmapped1", "unmapped2"})):
            # This should fail because we have un-mapped headers
            self.form_map.render_dict(data, allow_unknown=False)
