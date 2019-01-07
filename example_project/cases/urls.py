from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

from . import views
from .forms import CaseForm

from django_import_data.views import (
    GenericAuditGroupDetailView,
    GenericAuditGroupListView,
    GenericAuditListView,
    GenericAuditDetailView,
)

urlpatterns = [
    path("", RedirectView.as_view(url="/audit-groups")),
    path(
        "audit-groups/",
        GenericAuditGroupListView.as_view(),
        name="genericauditgroup_list",
    ),
    path(
        "audit-groups/<int:pk>/",
        GenericAuditGroupDetailView.as_view(),
        name="genericauditgroup_detail",
    ),
    path("audits/", GenericAuditListView.as_view(), name="genericaudit_list"),
    path("cases/", views.CaseListView.as_view(), name="case_list"),
    path("people/", views.PersonListView.as_view(), name="person_list"),
    path("structures/", views.StructureListView.as_view(), name="structure_list"),
    path("audits/", GenericAuditListView.as_view(), name="genericaudit_list"),
    path(
        "audits/<int:pk>/", GenericAuditDetailView.as_view(), name="genericaudit_detail"
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
        views.CaseCreateFromAuditView.as_view(),
        name="case_create_from_audit",
    ),
    path(
        "people/create-from-audit/<int:audit_pk>/",
        views.PersonCreateFromAuditView.as_view(),
        name="person_create_from_audit",
    ),
    path(
        "structure/create-from-audit/<int:audit_pk>/",
        views.StructureCreateFromAuditView.as_view(),
        name="structure_create_from_audit",
    ),
    path(
        "<str:model>/create-from-audit/<int:audit_pk>",
        views.CreateFromAuditRedirectView.as_view(),
        name="create_from_audit",
    ),
]
