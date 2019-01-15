from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from .models import (
    ModelImportAttempt,
    # ModelImporter,
    FileImporter,
    FileImportAttempt,
    RowData,
)


class CreateFromImportAttemptView(CreateView):
    def get_initial(self):
        self.model_import_attempt = get_object_or_404(
            ModelImportAttempt, id=self.kwargs["attempt_pk"]
        )
        return self.model_import_attempt.importee_field_data

    def form_valid(self, form):
        if self.model_import_attempt.model_importer.models.exists():
            messages.error(self.request, f"Error! Already exists yo")
            return redirect(
                "modelimporter_detail", pk=self.model_import_attempt.model_importer.id
            )

        # TODO: WTF is this
        self.object = form.save(commit=False)
        self.object.row_data = self.model_import_attempt.model_importer.row_data
        self.object.model_importers.set([self.model_import_attempt.model_importer])
        form.save()

        try:
            audit = ModelImportAttempt.objects.create(
                model_importer=self.model_import_attempt.model_importer,
                importee_field_data=form.cleaned_data,
                errors={},
            )
        except ValueError as error:
            messages.error(self.request, f"Error! {error}")
        else:
            messages.success(self.request, f"Created audit: {audit}")

        # From FormMixin
        return HttpResponseRedirect(self.get_success_url())


# class ModelImporterDetailView(DetailView):
#     model = ModelImporter
#     template_name = "modelimporter_detail.html"


# class ModelImporterListView(ListView):
#     model = ModelImporter
#     template_name = "modelimporter_list.html"


class ModelImportAttemptDetailView(DetailView):
    model = ModelImportAttempt
    template_name = "modelimportattempt_detail.html"


class ModelImportAttemptListView(ListView):
    model = ModelImportAttempt
    template_name = "modelimportattempt_list.html"


class RowDataDetailView(DetailView):
    model = RowData
    template_name = "rowdata_detail.html"


class RowDataListView(ListView):
    model = RowData
    template_name = "rowdata_list.html"


class FileImporterListView(ListView):
    model = FileImporter
    template_name = "cases/generic_list.html"


class FileImporterDetailView(DetailView):
    model = FileImporter
    template_name = "fileimporter_detail.html"


class FileImportAttemptListView(ListView):
    model = FileImportAttempt
    # TODO: BAD
    template_name = "cases/generic_list.html"


class FileImportAttemptDetailView(DetailView):
    model = FileImportAttempt
    template_name = "fileimportattempt_detail.html"
