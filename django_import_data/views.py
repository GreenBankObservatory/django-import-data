from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic import CreateView
from django.shortcuts import get_object_or_404, redirect

from .models import (
    GenericAuditGroup,
    GenericAudit,
    RowData,
    GenericAuditGroupBatch,
    GenericBatchImport,
)


class CreateFromAuditView(CreateView):
    def get_initial(self):
        self.audit = get_object_or_404(GenericAudit, id=self.kwargs["audit_pk"])
        return self.audit.auditee_fields

    def form_valid(self, form):
        if self.audit.audit_group.auditee:
            messages.error(self.request, f"Error! Already exists yo")
            return redirect("genericauditgroup_detail", pk=self.audit.audit_group.id)

        self.object = form.save(commit=False)
        self.object.row_data = self.audit.audit_group.row_data
        self.object.audit_groups.set([self.audit.audit_group])
        form.save()

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

        # From FormMixin
        return HttpResponseRedirect(self.get_success_url())


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


class RowDataDetailView(DetailView):
    model = RowData
    template_name = "rowdata_detail.html"


class RowDataListView(ListView):
    model = RowData
    template_name = "rowdata_list.html"


class GenericAuditGroupBatchListView(ListView):
    model = GenericAuditGroupBatch
    template_name = "cases/generic_list.html"


class GenericAuditGroupBatchDetailView(DetailView):
    model = GenericAuditGroupBatch
    template_name = "genericauditgroupbatch_detail.html"


class GenericBatchImportListView(ListView):
    model = GenericBatchImport
    template_name = "cases/generic_list.html"


class GenericBatchImportDetailView(DetailView):
    model = GenericBatchImport
    template_name = "genericbatchimport_detail.html"
