from django.urls import reverse
from django.views.generic import CreateView
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from django_import_data.views import CreateFromImportAttemptView

from .models import Person, Case, Structure
from .forms import PersonForm, CaseForm, StructureForm


class PersonDetailView(DetailView):
    model = Person
    template_name = "cases/generic_detail.html"


class CaseDetailView(DetailView):
    model = Case
    template_name = "cases/generic_detail.html"


class StructureDetailView(DetailView):
    model = Structure
    template_name = "cases/generic_detail.html"


class PersonListView(ListView):
    model = Person
    template_name = "cases/generic_list.html"


class CaseListView(ListView):
    model = Case
    template_name = "cases/generic_list.html"


class StructureListView(ListView):
    model = Structure
    template_name = "cases/generic_list.html"


class PersonCreateView(CreateView):
    # model = Person
    form_class = PersonForm


class PersonCreateFromImportAttemptView(CreateFromImportAttemptView):
    model = Person
    form_class = PersonForm
    template_name = "cases/generic_form.html"


class CaseCreateView(CreateView):
    # model = Case
    form_class = CaseForm


class CaseCreateFromImportAttemptView(CreateFromImportAttemptView):
    model = Case
    form_class = CaseForm
    template_name = "cases/generic_form.html"


class StructureDetailView(DetailView):
    model = Structure


class StructureCreateFromImportAttemptView(CreateFromImportAttemptView):
    model = Structure
    form_class = StructureForm
    template_name = "cases/generic_form.html"


class CreateFromAuditRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return reverse(
            f"{kwargs['model']}_create_from_audit",
            kwargs={"audit_pk": kwargs.get("audit_pk", None)},
        )
        # return super().get_redirect_url(*args, **kwargs)
