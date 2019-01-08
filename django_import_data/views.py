import json

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic import CreateView
from django.shortcuts import get_object_or_404, redirect
from django.forms import ValidationError

from .models import GenericAuditGroup, GenericAudit, RowAudit


class CreateFromAuditView(CreateView):
    def get_initial(self):
        audit = get_object_or_404(GenericAudit, id=self.kwargs["audit_pk"])
        self.audit = audit

        print("AUDIT", audit.auditee_fields)
        return audit.auditee_fields

    # def get_form(self, form_class=None):
    #     if form_class is None:
    #         form_class = self.get_form_class()
    #     return form_class(self.get_initial())

    def form_valid(self, form):
        if self.audit.audit_group.auditee:
            messages.error(self.request, f"Error! Already exists yo")
            to = self.request.META.get("HTTP_REFERER", "genericauditgroup_list")
            print("FSDJFDSLKJ", to)
            return redirect("genericauditgroup_detail", pk=self.audit.audit_group.id)
        response = super().form_valid(form)
        self.object.audit_groups.set([self.audit.audit_group])
        try:
            audit = GenericAudit.objects.create(
                audit_group=self.audit.audit_group,
                auditee_fields=form.cleaned_data,
                errors={},
            )
        except ValueError as error:
            messages.error(self.request, f"Error! {error}")
        else:
            messages.success(self.request, f"Created audit: {audit}")
        return response


class GenericAuditGroupDetailView(DetailView):
    model = GenericAuditGroup
    template_name = "genericauditgroup_detail.html"


class GenericAuditGroupListView(ListView):
    model = GenericAuditGroup
    template_name = "genericauditgroup_list.html"


class GenericAuditDetailView(DetailView):
    model = GenericAudit
    template_name = "genericaudit_detail.html"


class GenericAuditListView(ListView):
    model = GenericAudit
    template_name = "genericaudit_list.html"


class RowAuditDetailView(DetailView):
    model = RowAudit
    template_name = "rowaudit_detail.html"


class RowAuditListView(ListView):
    model = RowAudit
    template_name = "rowaudit_list.html"
