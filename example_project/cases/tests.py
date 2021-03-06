from collections import OrderedDict
from io import StringIO

from django.test import TestCase

from django_import_data import FormMapSet
from django_import_data.formmapset import flatten_dependencies
from django.contrib.contenttypes.models import ContentType

from .models import Case, Person, Structure
from importers.example_data_source.form_maps import (
    CaseFormMap,
    PersonFormMap,
    StructureFormMap,
)
from cases.management.commands.import_example_data import Command

from .forms import StructureForm
from django_import_data.models import (
    FileImporter,
    FileImportAttempt,
    FileImporterBatch,
    RowData,
    ModelImporter,
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
            path=path, importer_name="TestSanity"
        )
        self.assertIsNotNone(file_importer)
        self.assertEqual(file_importer.latest_file_import_attempt.imported_from, path)
        self.assertIsNotNone(file_import_attempt)
        self.assertEqual(file_import_attempt.imported_from, path)

        row_data = RowData.objects.create(
            file_import_attempt=file_import_attempt, row_num=0, data={"foo": "bar"}
        )

        case_importer, case_import_attempt = ModelImporter.objects.create_with_attempt(
            model=Case,
            importee_field_data={"foo": "bar"},
            errors={},
            error_summary={},
            row_data=row_data,
            imported_by="TestSanity",
        )

        self.assertIsNone(case_import_attempt.importee)
        case = Case.objects.create(
            case_num=123, model_import_attempt=case_import_attempt, subtype=1
        )
        self.assertIsNotNone(case_import_attempt.importee)
        self.assertIn(case_importer, row_data.model_importers.all())
        self.assertEqual(row_data.model_importers.count(), 1)

        structer_importer, structure_import_attempt = ModelImporter.objects.create_with_attempt(
            model=Structure,
            row_data=row_data,
            importee_field_data={"foo": "bar"},
            errors={},
            error_summary={},
            imported_by="TestSanity",
        )

        self.assertIsNone(structure_import_attempt.importee)
        structure = Structure.objects.create(
            location="foo", model_import_attempt=structure_import_attempt
        )
        self.assertIsNotNone(structure_import_attempt.importee)

        self.assertIn(structer_importer, row_data.model_importers.all())
        self.assertEqual(row_data.model_importers.count(), 2)

        self.assertEqual(Structure.objects.count(), 1)

        with self.assertRaisesRegex(ValueError, "Mismatched"):
            Case.objects.create(
                case_num=123, model_import_attempt=structure_import_attempt
            )

        expected_deletions = (
            8,
            {
                # This is the important one: we _must_ cascade to our
                # importees!
                "cases.Case": 1,
                "django_import_data.ModelImportAttempt": 2,
                "cases.Structure": 1,
                "django_import_data.ModelImporter": 2,
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


from django.core.management import call_command


class TestImportExampleData(TestCase):
    """End-to-end tests using the import_example_data importer"""

    def assertDictIsSubset(self, first, second):
        return self.assertLessEqual(
            first.items(),
            second.items(),
            f"Items missing from second item: {set(first.items()).difference(second.items())}",
        )

    def test_good_data(self):
        self.assertEqual(Structure.objects.count(), 0)
        self.assertEqual(Person.objects.count(), 0)
        self.assertEqual(Case.objects.count(), 0)

        call_command(
            "import_example_data",
            "/home/sandboxes/tchamber/repos/django-import-data/example_project/importers/example_data_source/test_data.csv",
            verbosity=3,
        )

        # 1 input file yields 1 file importer
        self.assertEqual(FileImporter.objects.count(), 1)
        # 1 attempt to import this input file yields 1 file import attempt
        self.assertEqual(FileImportAttempt.objects.count(), 1)
        # 1 row in the file during this attempt yields 1 RowData
        self.assertEqual(RowData.objects.count(), 1)
        # 3 Models are defined for each row, so we expect 3 model importers
        self.assertEqual(ModelImporter.objects.count(), 3)
        # 1 attempt each yields 3 model import attempts
        self.assertEqual(ModelImportAttempt.objects.count(), 3)

        # Structure should be created
        self.assertEqual(Structure.objects.count(), 1)
        # Person should be created
        self.assertEqual(Person.objects.count(), 1)
        # Case should be created
        self.assertEqual(Case.objects.count(), 1)

        structure_values = Structure.objects.values().first()
        expected_structure_values = {"location": "(38.7, 78.1)"}
        self.assertDictIsSubset(expected_structure_values, structure_values)

        person_values = Person.objects.values().first()
        expected_person_values = {
            "name": "Foo Bar Baz",
            "phone": "123456789",
            "email": "foo@bar.baz",
            "city": "Atlanta",
            "street": "123 Foobar St",
            "zip": "30078",
            "state": "GA",
        }
        self.assertDictIsSubset(expected_person_values, person_values)

        case_values = Case.objects.values().first()
        expected_case_values = {
            "case_num": 1,
            "status": "complete",
            "type": "A",
            "subtype": 1,
        }
        self.assertDictIsSubset(expected_case_values, case_values)

    def test_bad_email_no_durable(self):
        with self.assertRaisesRegex(
            ValueError, "Row 2 of file test_data_bad.csv handled, but had 1 errors"
        ):
            # Note that no --durable is given here, so we will not be continuing past the bad email value.
            # PersonForm should raise an error
            call_command(
                "import_example_data",
                "/home/sandboxes/tchamber/repos/django-import-data/example_project/importers/example_data_source/test_data_bad.csv",
                verbosity=3,
            )

    def test_bad_email_durable(self):
        """Ensure proper handling of Person with invalid email. durable=True"""

        path = "/home/sandboxes/tchamber/repos/django-import-data/example_project/importers/example_data_source/test_data_bad.csv"
        call_command(
            "import_example_data",
            path,
            verbosity=3,
            # Durable will force processing to continue past otherwise-fatal errors. In this case, we have a bad
            # email value that should get caught by the PersonForm and raise a ValueError. But, we
            # will ignore that error and continue on
            durable=True,
        )

        ### File Importer ###
        # 1 input file yields 1 file importer
        self.assertEqual(FileImporter.objects.count(), 1)
        file_importer = FileImporter.objects.first()
        self.assertEqual(file_importer.status, FileImporter.STATUSES.rejected.db_value)
        expected_fi_errors_by_row = {
            2: {
                "form_errors": [
                    {
                        "alias": ["E-mail"],
                        "field": "email",
                        "value": "not an email",
                        "errors": ["ValidationError(['Enter a valid email address.'])"],
                    }
                ]
            }
        }
        self.assertEqual(
            file_importer.errors_by_row_as_dict(), expected_fi_errors_by_row
        )

        ### File Import Attempt ###
        # 1 attempt to import this input file yields 1 file import attempt
        self.assertEqual(FileImportAttempt.objects.count(), 1)
        file_import_attempt = FileImportAttempt.objects.first()
        self.assertEqual(
            file_import_attempt.status, FileImportAttempt.STATUSES.rejected.db_value
        )
        # Should be the same as for the FI
        self.assertEqual(
            file_import_attempt.errors_by_row_as_dict(), expected_fi_errors_by_row
        )

        ### Row Data ###
        # 1 row in the file during this attempt yields 1 RowData
        self.assertEqual(RowData.objects.count(), 1)
        row_data = RowData.objects.first()
        # row_data.data should be _exactly the same_ as the data in the file!
        self.assertEqual(row_data.data, list(Command.load_rows(path))[0])
        self.assertEqual(row_data.status, RowData.STATUSES.rejected.db_value)
        actual_errors_by_alias = row_data.errors_by_alias()
        expected_errors_by_alias = {
            "case_num": [
                {
                    "field": "case_num",
                    "value": None,
                    "errors": ["ValidationError(['This field is required.'])"],
                    "error_type": "form",
                },
                {
                    "error": "ValueError(\"invalid literal for int() with base 10: 'potato'\")",
                    "converter": "convert_case_num",
                    "to_fields": ["case_num"],
                    "from_fields": ["case_num"],
                    "error_type": "conversion",
                },
            ],
            "E-mail": [
                {
                    "field": "email",
                    "value": "not an email",
                    "errors": ["ValidationError(['Enter a valid email address.'])"],
                    "error_type": "form",
                }
            ],
        }
        self.assertEqual(actual_errors_by_alias, expected_errors_by_alias)
        ### Model Importer ###
        # 3 Models are defined for each row, so we expect 3 model importers
        self.assertEqual(ModelImporter.objects.count(), 3)

        ### Model Import Attempt ###
        # 1 attempt each yields 3 model import attempts
        self.assertEqual(ModelImportAttempt.objects.count(), 3)
        # 1 of these failed (had no created model). Thus, we expect that...
        # ...the number of MIAs with _no_ importee (imported model) should be 2...
        self.assertEqual(ModelImportAttempt.objects.get_num_without_importee(), 2)
        # ...and the number of MIAs in a "rejected" state should be 2
        self.assertEqual(ModelImportAttempt.objects.get_num_rejected(), 2)
        # 2 of these succeeded (have created model). Thus, we expect that...
        # ...the number of MIAs with an importee (imported model) should be 1...
        self.assertEqual(ModelImportAttempt.objects.get_num_with_importee(), 1)
        # ...and the number of MIAs in a "successful" state should be 1
        self.assertEqual(ModelImportAttempt.objects.get_num_successful(), 1)

        # Here, instead of checking the Person instance (since there isn't one),
        # we check to ensure that the appropriate errors were set for the MIA
        person_mia = ModelImportAttempt.objects.get(
            content_type=ContentType.objects.get_for_model(Person)
        )
        # We expect the model import attempt to contain the following errors,
        # resulting from the invalid email in the row from the CSV file
        expected_person_mia_errors = {
            "form_errors": [
                {
                    "alias": ["E-mail"],
                    "field": "email",
                    "value": "not an email",
                    "errors": ["ValidationError(['Enter a valid email address.'])"],
                }
            ]
        }
        self.assertEqual(person_mia.errors, expected_person_mia_errors)

        # There should be exactly one Case MIA, and it should have no errors
        case_mia = ModelImportAttempt.objects.get(
            content_type=ContentType.objects.get_for_model(Case)
        )
        expected_case_mia_errors = {
            "form_errors": [
                {
                    "alias": ["case_num"],
                    "field": "case_num",
                    "value": None,
                    "errors": ["ValidationError(['This field is required.'])"],
                }
            ],
            "conversion_errors": [
                {
                    "error": "ValueError(\"invalid literal for int() with base 10: 'potato'\")",
                    "aliases": {"case_num": ["case_num"]},
                    "converter": "convert_case_num",
                    "to_fields": ["case_num"],
                    "from_fields": ["case_num"],
                }
            ],
        }
        self.assertEqual(case_mia.errors, expected_case_mia_errors)

        # There should be exactly one Structure MIA, and it should have no errors
        structure_mia = ModelImportAttempt.objects.get(
            content_type=ContentType.objects.get_for_model(Structure)
        )
        expected_structure_mia_errors = {}
        self.assertEqual(structure_mia.errors, expected_structure_mia_errors)

        ### Audited Models ###
        # No person should have been created due to the invalid email
        self.assertEqual(Person.objects.count(), 0)

        # Structure should be created
        self.assertEqual(Structure.objects.count(), 1)
        structure_values = Structure.objects.values().first()
        expected_structure_values = {"location": "(38.7, 78.1)"}
        self.assertDictIsSubset(expected_structure_values, structure_values)

        # Case should not be created due to invalid case number and invalid sub type
        self.assertEqual(Case.objects.count(), 0)

    def _test_file_with_no_rows(self):
        # Behavior should be identical regardles of durable value, so we've
        # consolidated checks into this one function

        ### File Importer ###
        # 1 input file yields 1 file importer
        self.assertEqual(FileImporter.objects.count(), 1)
        file_importer = FileImporter.objects.first()
        self.assertEqual(file_importer.status, FileImporter.STATUSES.empty.db_value)

        ### File Import Attempt ###
        # 1 attempt to import this input file yields 1 file import attempt
        self.assertEqual(FileImportAttempt.objects.count(), 1)
        file_import_attempt = FileImportAttempt.objects.first()
        self.assertEqual(
            file_import_attempt.status, FileImportAttempt.STATUSES.empty.db_value
        )

        ### Row Data ###
        # 0 row in the file during this attempt yields 0 RowData
        self.assertEqual(RowData.objects.count(), 0)

        ### Model Importer ###
        # 3 Models are defined for each row, so we expect 3 model importers
        self.assertEqual(ModelImporter.objects.count(), 0)

        ### Model Import Attempt ###
        # 1 attempt each yields 3 model import attempts
        self.assertEqual(ModelImportAttempt.objects.count(), 0)

    def test_file_with_no_rows_no_durable(self):
        """Test file with headers, but no data rows; durable=False"""

        call_command(
            "import_example_data",
            "/home/sandboxes/tchamber/repos/django-import-data/example_project/importers/example_data_source/test_data_no_rows.csv",
            verbosity=3,
        )

        self._test_file_with_no_rows()

    def test_file_with_no_rows_durable(self):
        """Test file with headers, but no data rows; durable=True"""

        path = "/home/sandboxes/tchamber/repos/django-import-data/example_project/importers/example_data_source/test_data_no_rows.csv"
        call_command(
            "import_example_data",
            path,
            verbosity=3,
            # Durable will force processing to continue past otherwise-fatal errors. In this case, we have a bad
            # email value that should get caught by the PersonForm and raise a ValueError. But, we
            # will ignore that error and continue on
            durable=True,
        )

        self._test_file_with_no_rows()
