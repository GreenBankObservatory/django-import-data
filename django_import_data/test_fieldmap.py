from pprint import pprint

from unittest import TestCase
from . import (
    FormMap,
    FieldMap,
    OneToOneFieldMap,
    OneToManyFieldMap,
    ManyToOneFieldMap,
    ManyToManyFieldMap,
)
from .converters import handle_dms, handle_location


class TestFieldMap(TestCase):
    def test_bare_init(self):
        with self.assertRaisesRegex(TypeError, "required"):
            FieldMap()

    def test_init_no_strings(self):
        with self.assertRaisesRegex(
            TypeError, "to_fields and from_fields should not be strings!"
        ):
            FieldMap(from_fields=("foo", "bar"), to_fields="bar", converter=lambda x: x)

    def test_init_simple_no_aliases(self):
        FieldMap(from_fields=("foo", "bar"), to_fields=("bar",), converter=lambda x: x)

    def test_init_simple_with_aliases(self):
        # Should work since from_fields is "simple"
        FieldMap(
            from_fields=("foo", "bar"),
            to_fields=("bar",),
            aliases={"foo": ("FOO",)},
            converter=lambda x: x,
        )

    def test_init_compound_with_aliases(self):
        # Should fail since from_fields is "compound"
        with self.assertRaisesRegex(ValueError, "compound"):
            FieldMap(
                from_fields={"foo": ("FOO",), "bar": ("bar",)},
                to_fields=("bar",),
                aliases={"foo": ("FOO",)},
                converter=lambda x: x,
            )

    def test_init_compound_no_aliases(self):
        # Should work since aliases isn't given
        FieldMap(
            from_fields={"foo": ("FOO",), "bar": ("bar",)},
            to_fields=("bar",),
            converter=lambda x: x,
        )

    def test_invert_aliases(self):
        aliases = {"latitude": ("LAT", "lat."), "longitude": ("LONG", "long.")}
        actual = FieldMap._invert_aliases(aliases)
        expected = {
            "LAT": "latitude",
            "lat.": "latitude",
            "LONG": "longitude",
            "long.": "longitude",
        }

        return self.assertEqual(actual, expected)

    def test_split_from_fields(self):
        actual = FieldMap._split_from_fields(
            from_fields={"latitude": ["lat", "LAT"], "longitude": ["long", "LONG"]}
        )
        expected = (
            # aliases
            {
                "lat": "latitude",
                "LAT": "latitude",
                "long": "longitude",
                "LONG": "longitude",
            },
            # from_fields
            ("latitude", "longitude"),
        )
        self.assertEqual(actual, expected)

    def test_split_from_fields_non_dict(self):
        with self.assertRaises(ValueError):
            FieldMap._split_from_fields(from_fields=("latitude", "longitude"))

    def test_split_from_fields_hetero(self):
        actual_aliases, actual_from_fields = FieldMap._split_from_fields(
            {"latitude": ["lat", "LAT"], "longitude": None}
        )
        expected_aliases = {"lat": "latitude", "LAT": "latitude"}
        expected_from_fields = ("latitude", "longitude")
        self.assertEqual(actual_aliases, expected_aliases)
        self.assertEqual(actual_from_fields, expected_from_fields)

    def test_unalias_basic(self):
        data = {"lat": "11 22 33", "long": "44 55 66"}
        field_map = FieldMap(
            to_fields=("location",),
            converter=handle_location,
            from_fields={"latitude": ["lat", "LAT"], "longitude": ["long", "LONG"]},
        )
        actual = field_map.unalias(data)
        expected = {"latitude": "11 22 33", "longitude": "44 55 66"}
        self.assertEqual(actual, expected)

    def test_unalias_unknown_fields(self):
        data = {"lat": "11 22 33", "long": "44 55 66", "potato": "POTATO"}
        field_map = FieldMap(
            to_fields=("location",),
            converter=handle_location,
            from_fields={"latitude": ["lat", "LAT"], "longitude": ["long", "LONG"]},
        )
        with self.assertRaisesRegex(ValueError, "not a known field"):
            field_map.unalias(data, allow_unknown=False)

        actual = field_map.unalias(data)
        expected = {"latitude": "11 22 33", "longitude": "44 55 66"}
        self.assertEqual(actual, expected)

    def test_unalias_no_aliases(self):
        data = {"latitude": "11 22 33", "longitude": "44 55 66", "potato": "POTATO"}
        field_map = FieldMap(
            from_fields=("latitude", "longitude"),
            to_fields=("location",),
            converter=handle_location,
        )
        actual = field_map.unalias(data)
        expected = {"latitude": "11 22 33", "longitude": "44 55 66"}
        self.assertEqual(actual, expected)

    def test_unknown_fields(self):
        data = {"latitude": "11 22 33", "longitude": "44 55 66", "potato": "POTATO"}
        field_map = FieldMap(
            from_fields=("latitude", "longitude"),
            to_fields=("location",),
            converter=handle_location,
        )
        actual = field_map.get_unknown_fields(data)
        expected = {"potato"}
        self.assertEqual(actual, expected)


class TestManyToManyFieldMap(TestCase):
    def test_from_fields_to_fields_default_converter(self):
        with self.assertRaises(ValueError):
            ManyToManyFieldMap(
                from_fields=("latitude", "longitude"),
                to_fields=("lat_m", "lat_s", "long_d", "long_m", "long_s"),
            )


class TestOneToManyFieldMap(TestCase):
    def test_from_field_to_fields_with_converter(self):
        field_map = OneToManyFieldMap(
            from_field="nrqz_id",
            converter=lambda nrqz_id: dict(
                case_num=nrqz_id[0:4], site_name=nrqz_id[5:]
            ),
            to_fields=("case_num", "site_name"),
        )
        actual = field_map.render(dict(nrqz_id="1111 Mr. Tower"))
        expected = dict(case_num="1111", site_name="Mr. Tower")
        self.assertEqual(actual, expected)

    def test_render(self):
        data = {"lat": "11 22 33", "long": "44 55 66"}
        field_map = ManyToOneFieldMap(
            to_field="location",
            converter=handle_location,
            from_fields={"latitude": ["lat", "LAT"], "longitude": ["long", "LONG"]},
        )
        actual = field_map.render(data)
        expected = {"location": (data["lat"], data["long"])}
        self.assertEqual(actual, expected)


class TestManyToOneFieldMap(TestCase):
    def test_from_fields_to_field_with_converter(self):
        field_map = ManyToOneFieldMap(
            from_fields=("latitude", "longitude"),
            converter=lambda latitude, longitude: dict(location=(latitude, longitude)),
            to_field="location",
        )
        actual = field_map.render(dict(latitude="11 22 33", longitude="44 55 66"))
        expected = dict(location=("11 22 33", "44 55 66"))
        self.assertEqual(actual, expected)

    def test_render(self):
        data = {"LAT": 30.1, "long": 30.2}
        field_map = ManyToOneFieldMap(
            converter=handle_location,
            to_field="location",
            from_fields={"latitude": ["lat", "LAT"], "longitude": ["long", "LONG"]},
        )
        actual = field_map.render(data)
        expected = {"location": (data["LAT"], data["long"])}
        self.assertEqual(actual, expected)


class TestManyToManyFieldMap(TestCase):
    def test_from_fields_to_fields_with_converter(self):
        field_map = ManyToManyFieldMap(
            from_fields=("latitude", "longitude"),
            converter=lambda latitude, longitude: dict(
                lat_d=latitude[0:2],
                lat_m=latitude[2:4],
                lat_s=latitude[4:6],
                long_d=longitude[0:2],
                long_m=longitude[2:4],
                long_s=longitude[4:6],
            ),
            to_fields=("lat_m", "lat_s", "long_d", "long_m", "long_s"),
        )
        actual = field_map.render(dict(latitude="112233", longitude="445566"))
        expected = dict(
            lat_d="11", lat_m="22", lat_s="33", long_d="44", long_m="55", long_s="66"
        )
        self.assertEqual(actual, expected)

    # TODO: This is contrived; come up with a better example! (Could be split into two fieldmaps)
    def test_render(self):
        data = {"LAT": "30 31 32", "long.": "33 34 35"}
        field_map = ManyToManyFieldMap(
            from_fields={"latitude": ("LAT", "lat."), "longitude": ("LONG", "long.")},
            converter=handle_dms,
            to_fields=("lat_d", "lat_m", "lat_s", "long_d", "long_m", "long_s"),
        )
        actual = field_map.render(data)
        expected = {
            "lat_d": "30",
            "lat_m": "31",
            "lat_s": "32",
            "long_d": "33",
            "long_m": "34",
            "long_s": "35",
        }
        self.assertEqual(actual, expected)


class TestOneToOneFieldMap(TestCase):
    def test_init_bare(self):
        with self.assertRaises(TypeError):
            OneToOneFieldMap()

    def test_render_no_to_field_no_aliases(self):
        data = {"foo": "baz"}
        field_map = OneToOneFieldMap(from_field="foo")
        # Test data
        actual = field_map.render(data)
        expected = {"foo": data["foo"]}
        self.assertEqual(actual, expected)

    def test_render_no_to_field_with_aliases(self):
        data = {"foo": "baz"}
        field_map = OneToOneFieldMap(from_field={"foo": ("Foo",)})
        # Test data
        actual = field_map.render(data)
        expected = {"foo": data["foo"]}
        self.assertEqual(actual, expected)

    def test_render_with_aliases(self):
        data = {"Bar": "baz"}
        field_map = OneToOneFieldMap(from_field={"foo": ("Foo", "Bar")}, to_field="foo")
        # Test data
        actual = field_map.render(data)
        expected = {"foo": data["Bar"]}
        self.assertEqual(actual, expected)

    def test_reject_multiple_alias_matches(self):
        data = {"Bar": "bar", "Baz": "baz", "Bat": "boo"}
        field_map = OneToOneFieldMap(from_field={"foo": ("Bar", "Baz")}, to_field="foo")
        with self.assertRaises(ValueError):
            field_map.render(data)

        field_map.render(data)
        actual = field_map.render(data, allow_multiple_aliases_for_field=True)
        expected = {"foo": "baz"}
        self.assertEqual(actual, expected)
