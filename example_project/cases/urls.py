from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

from . import views
from .forms import CaseForm

from django_import_data.views import (
    # ModelImporterDetailView,
    # ModelImporterListView,
    ModelImportAttemptListView,
    ModelImportAttemptDetailView,
    FileImporterListView,
    FileImporterDetailView,
    FileImportAttemptListView,
    FileImportAttemptDetailView,
)

urlpatterns = [
    path("", RedirectView.as_view(url="/audit-groups")),
    # path("audit-groups/", ModelImporterListView.as_view(), name="ModelImporter_list"),
    # path(
    #     "audit-groups/<int:pk>/",
    #     ModelImporterDetailView.as_view(),
    #     name="ModelImporter_detail",
    # ),
    path(
        "audits/", ModelImportAttemptListView.as_view(), name="ModelImportAttempt_list"
    ),
    path("cases/", views.CaseListView.as_view(), name="case_list"),
    path("people/", views.PersonListView.as_view(), name="person_list"),
    path("structures/", views.StructureListView.as_view(), name="structure_list"),
    path(
        "audits/", ModelImportAttemptListView.as_view(), name="ModelImportAttempt_list"
    ),
    path(
        "audits/<int:pk>/",
        ModelImportAttemptDetailView.as_view(),
        name="ModelImportAttempt_detail",
    ),
    path("cases/create", views.CaseCreateView.as_view(), name="case_create"),
    path("cases/<int:pk>/", views.CaseDetailView.as_view(), name="case_detail"),
    path("people/<int:pk>/", views.PersonDetailView.as_view(), name="person_detail"),
    path(
        "structures/<int:pk>/",
        views.StructureDetailView.as_view(),
        name="structure_detail",
    ),
    path(
        "cases/create-from-audit/<int:audit_pk>/",
        views.CaseCreateFromImportAttemptView.as_view(),
        name="case_create_from_audit",
    ),
    path(
        "people/create-from-audit/<int:audit_pk>/",
        views.PersonCreateFromImportAttemptView.as_view(),
        name="person_create_from_audit",
    ),
    path(
        "structure/create-from-audit/<int:audit_pk>/",
        views.StructureCreateFromImportAttemptView.as_view(),
        name="structure_create_from_audit",
    ),
    path("batches/", FileImporterListView.as_view(), name="FileImporter_list"),
    path(
        "batches/<int:pk>/",
        FileImporterDetailView.as_view(),
        name="FileImporter_detail",
    ),
    path(
        "batch-imports/",
        FileImportAttemptListView.as_view(),
        name="FileImportAttempt_list",
    ),
    path(
        "batch-imports/<int:pk>/",
        FileImportAttemptDetailView.as_view(),
        name="FileImportAttempt_detail",
    ),
]
