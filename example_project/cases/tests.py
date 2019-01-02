from collections import OrderedDict

from django.test import TestCase

from django_import_data import FormMapSet
from django_import_data.formmapset import flatten_dependencies

from .models import Case, Person, Structure
from .formmaps import CaseFormMap, PersonFormMap, StructureFormMap
from .forms import StructureForm

row = {
    "first_name": "Foo",
    "middle_name": "Bar",
    "last_name": "Baz",
    "email": "foo@bar.baz",
    "case_num": "1",
    "completed": "True",
    "type": "A 1",
    "afsdf.": "123 Foobar St, Atlanta, GA, 30078",
    "letter1": "/home/foo/foo.txt",
    "latitude": "38.7",
    "longitude": "78.1",
}


class TestFormMaps(TestCase):
    def test_person_form_map(self):
        form_map = PersonFormMap()
        person = form_map.save(row)
        self.assertEqual(
            # Just compare string representations since we can't do DB-level
            # comparisons here (Django uses pk values for equality)
            str(person),
            str(Person(name="Foo Bar Baz", email="foo@bar.baz")),
        )

    def test_case_form_map(self):
        form_map = CaseFormMap()
        case = form_map.save(row)
        self.assertEqual(
            # Just compare string representations since we can't do DB-level
            # comparisons here (Django uses pk values for equality)
            str(case),
            str(Case(case_num=1)),
        )

    def test_structure_form_map(self):
        form_map = StructureFormMap()
        structure = form_map.save(row)
        self.assertEqual(
            # Just compare string representations since we can't do DB-level
            # comparisons here (Django uses pk values for equality)
            str(structure),
            str(Structure(location=("38.7", "78.1"))),
        )


# class TestFormMapSets(TestCase):
#     # def setUp(self):
#     #     self.person_form_map = PersonFormMap()
#     #     self.case_form_map = CaseFormMap()

#     def test_foo(self):
#         fms = FormMapSet(
#             form_maps={"applicant": PersonFormMap(), "case": CaseFormMap()},
#             dependencies={"case": ("applicant",)},
#         )
#         fms.report()
#         foo = fms.render(row)
#         print(foo)

#     def test_flatten(self):
#         print(flatten_dependencies({"case": ("applicant",)}))


# class TestStructureForm(TestCase):
#     def test(self):
#         sf = StructureForm({"longitude": "30", "latitude": "70"})
#         print(sf.data)
#         print(sf.is_valid())
#         print(sf.errors.as_data())
