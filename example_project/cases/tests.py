from collections import OrderedDict
from io import StringIO

from django.test import TestCase

from django_import_data import FormMapSet
from django_import_data.formmapset import flatten_dependencies
from django.contrib.contenttypes.models import ContentType

from .models import Case, Person, Structure
from .formmaps import CaseFormMap, PersonFormMap, StructureFormMap
from .forms import StructureForm
from django_import_data.models import (
    FileImporter,
    FileImportAttempt,
    RowData,
    ModelImportAttempt,
)


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


# class TestFormMaps(TestCase):
#     def test_person_form_map(self):
#         form_map = PersonFormMap()
#         person = form_map.save(row)
#         self.assertEqual(
#             # Just compare string representations since we can't do DB-level
#             # comparisons here (Django uses pk values for equality)
#             str(person),
#             str(Person(name="Foo Bar Baz", email="foo@bar.baz")),
#         )

#     def test_case_form_map(self):
#         form_map = CaseFormMap()
#         case = form_map.save(row)
#         self.assertEqual(
#             # Just compare string representations since we can't do DB-level
#             # comparisons here (Django uses pk values for equality)
#             str(case),
#             str(Case(case_num=1)),
#         )

#     def test_structure_form_map(self):
#         form_map = StructureFormMap()
#         structure = form_map.save(row)
#         self.assertEqual(
#             # Just compare string representations since we can't do DB-level
#             # comparisons here (Django uses pk values for equality)
#             str(structure),
#             str(Structure(location=("38.7", "78.1"))),
#         )


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


# class TestCaseAuditGroup(TestCase):
#     # def setUp(self):
#     #     self.case = Case.objects.create(case_num=123)

#     def test_foo(self):
#         case = Case.objects.create_with_audit(case_num=123)
#         self.assertIsInstance(case, Case)
#         self.assertIsInstance(case.audit_group, GenericAuditGroup)


# class TestGenericAuditGroupBatch(TestCase):
#     def setUp(self):
#         self.csv1 = {
#             "first_name": "Thomas",
#             "middle_name": "Bar",
#             "last_name": "Baz",
#             "phone_number": "123456789",
#             "email": "thomas@thomas.com",
#             "case_num": "CASE#123123",
#             "latitude": "38.1",
#             "longitude": "72.8",
#         }

#         self.csv2 = {
#             "first_name": "Bill",
#             # NOTE: Missing middle_name!
#             # "middle_name": "Bar",
#             "last_name": "Baz",
#             "phone": "758586998",
#             # NOTE: Invalid email!
#             "email": "foo@bar",
#             "case": "CASE#456456",
#             "latitude": "38.2",
#             "longitude": "78.5",
#         }

#         self.cfm = CaseFormMap()
#         self.pfm = PersonFormMap()
#         self.sfm = StructureFormMap()

#     def test_clean(self):
#         row_data = RowData.objects.create(data=self.csv1)
#         batch = GenericAuditGroupBatch.objects.create()
#         batch_import = batch.gen_import(path="/test/")
#         self.assertEqual(batch_import.genericauditgroup_audit_groups.count(), 0)

#         applicant, applicant_audit = self.pfm.save_with_audit(
#             self.csv1, row_data=row_data, batch_import=batch_import
#         )
#         self.assertIsNotNone(applicant)
#         self.assertEqual(applicant.name, "Thomas Bar Baz")
#         self.assertEqual(batch_import.genericauditgroup_audit_groups.count(), 1)

#         structure, structure_audit = self.sfm.save_with_audit(
#             self.csv1,
#             row_data=row_data,
#             extra={"applicant": applicant.id if applicant else None},
#             batch_import=batch_import,
#         )
#         self.assertIsNotNone(structure)
#         self.assertEqual(structure.location, "(38.1, 72.8)")
#         self.assertEqual(batch_import.genericauditgroup_audit_groups.count(), 2)

#         case, case_audit = self.cfm.save_with_audit(
#             self.csv1,
#             row_data=row_data,
#             extra={"applicant": applicant.id, "structure": structure.id},
#             batch_import=batch_import,
#         )
#         self.assertIsNotNone(case)
#         self.assertEqual(case.case_num, 123_123)

#         self.assertEqual(batch_import.genericauditgroup_audit_groups.count(), 3)

#         self.assertEqual(batch_import.status, "created_clean")

#     def test_error_in_applicant(self):
#         row_data = RowData.objects.create(data=self.csv2)
#         batch = GenericAuditGroupBatch.objects.create()
#         batch_import = batch.gen_import(path="/test/")
#         self.assertEqual(batch_import.genericauditgroup_audit_groups.count(), 0)

#         applicant, applicant_audit = self.pfm.save_with_audit(
#             self.csv2, row_data=row_data, batch_import=batch_import
#         )
#         # No applicant should have been created, because we expect there to be errors
#         self.assertIsNone(applicant)
#         # There should instead be an Audit created
#         self.assertIsNotNone(applicant_audit)

#         # Exactly one conversion error should have occurred
#         self.assertEqual(len(applicant_audit.errors["conversion_errors"]), 1)
#         # We expect this error's value to be about an unmapped header
#         self.assertEqual(
#             next(iter(applicant_audit.errors["conversion_errors"].values())),
#             "ValueError('Unmapped headers!',)",
#         )

#         # Exactly one form error should be reported
#         self.assertEqual(len(applicant_audit.errors["form_errors"]), 1)
#         # We expect this error to be for the email field
#         self.assertEqual(applicant_audit.errors["form_errors"][0]["field"], "email")

#         # Audit group should still be created
#         self.assertEqual(batch_import.genericauditgroup_audit_groups.count(), 1)

#         # We expect the batch imported to be "rejected", since at least
#         # error occurred
#         self.assertEqual(batch_import.status, "rejected")

#         # We expect the AuditGroup status to be rejected also
#         self.assertEqual(
#             batch_import.genericauditgroup_audit_groups.first().status, "rejected"
#         )

#         # And, of course, there should be a single Audit created...
#         self.assertEqual(
#             batch_import.genericauditgroup_audit_groups.first().audits.count(), 1
#         )
#         # ...with a rejected status
#         self.assertEqual(
#             batch_import.genericauditgroup_audit_groups.first().audits.first().status,
#             "rejected",
#         )


class TestSanity(TestCase):
    def test_sanity(self):
        path = "/foo/bar.txt"
        file_importer, file_import_attempt = FileImporter.objects.create_with_attempt(
            path=path
        )
        self.assertIsNotNone(file_importer)
        self.assertEqual(file_importer.latest_file_import_attempt.imported_from, path)
        self.assertIsNotNone(file_import_attempt)
        self.assertEqual(file_import_attempt.imported_from, path)

        row_data = RowData.objects.create(
            file_import_attempt=file_import_attempt, data={"foo": "bar"}
        )

        case_import_attempt = ModelImportAttempt.objects.create_for_model(
            model=Case,
            row_data=row_data,
            file_import_attempt=file_import_attempt,
            importee_field_data={"foo": "bar"},
            errors={},
            error_summary={},
        )

        self.assertIsNone(case_import_attempt.importee)
        case = Case.objects.create(
            case_num=123, model_import_attempt=case_import_attempt
        )
        self.assertIsNotNone(case_import_attempt.importee)
        self.assertIn(case_import_attempt, row_data.import_attempts.all())
        self.assertEqual(row_data.import_attempts.count(), 1)

        structure_import_attempt = ModelImportAttempt.objects.create_for_model(
            model=Structure,
            row_data=row_data,
            file_import_attempt=file_import_attempt,
            importee_field_data={"foo": "bar"},
            errors={},
            error_summary={},
        )

        self.assertIsNone(structure_import_attempt.importee)
        structure = Structure.objects.create(
            location="foo", model_import_attempt=structure_import_attempt
        )
        self.assertIsNotNone(structure_import_attempt.importee)

        self.assertIn(structure_import_attempt, row_data.import_attempts.all())
        self.assertEqual(row_data.import_attempts.count(), 2)

        self.assertEqual(Structure.objects.count(), 1)

        with self.assertRaisesRegex(ValueError, "Mismatched"):
            Case.objects.create(
                case_num=123, model_import_attempt=structure_import_attempt
            )

        expected_deletions = (
            6,
            {
                # This is the important one: we _must_ cascade to our
                # importees!
                "cases.Case": 1,
                "cases.Structure": 1,
                "django_import_data.ModelImportAttempt": 2,
                "django_import_data.RowData": 1,
                "django_import_data.FileImportAttempt": 1,
            },
        )
        actual_deletions = file_import_attempt.delete()
        self.assertEqual(actual_deletions, expected_deletions)

        # Sanity check to make sure we have no stragglers
        self.assertEqual(Case.objects.count(), 0)
        self.assertEqual(Structure.objects.count(), 0)
        self.assertEqual(ModelImportAttempt.objects.count(), 0)
        self.assertEqual(RowData.objects.count(), 0)
        self.assertEqual(FileImportAttempt.objects.count(), 0)
