from collections import OrderedDict

from django.test import TestCase

from django_import_data import FormMapSet
from django_import_data.formmapset import flatten_dependencies

from .formmaps import CaseFormMap, CaseGroupFormMap, PersonFormMap, AttachmentFormMap

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
}


class TestFormMaps(TestCase):
    def test_foo(self):
        form_map = PersonFormMap()
        foo = form_map.render(row)
        print(form_map)
        print(foo.data)

    def test_bar(self):
        form_map = CaseFormMap()
        foo = form_map.render(row)
        # print(foo.data)
        print(form_map)
        print(foo.data)


class TestFormMapSets(TestCase):
    # def setUp(self):
    #     self.person_form_map = PersonFormMap()
    #     self.case_form_map = CaseFormMap()

    def test_foo(self):
        fms = FormMapSet(
            form_maps={
                "applicant": PersonFormMap(),
                "case": CaseFormMap(),
                "attachment": AttachmentFormMap(),
                "group": CaseGroupFormMap(),
            },
            dependencies={"case": ("applicant", "attachment", "group")},
        )
        fms.report()
        foo = fms.render(row)
        print(foo)

    def test_flatten(self):
        print(
            flatten_dependencies({"case_group": {"case": ("applicant", "attachment")}})
        )
