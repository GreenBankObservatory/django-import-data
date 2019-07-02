from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, FormView, UpdateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from .models import (
    ModelImportAttempt,
    FileImporter,
    FileImportAttempt,
    FileImportBatch,
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


class FileImporterCreateView(CreateView):
    model = FileImporter
    fields = "importer_name"
    template_name = "fileimporter_form.html"


def acknowledge_file_import_attempt(request, pk):
    file_import_attempt = get_object_or_404(FileImportAttempt, id=pk)
    if request.method == "POST":
        acknowledge = request.POST.get("acknowledge", None)
        if acknowledge is None:
            messages.error(request, "Malformed request")
        else:
            if acknowledge == "Acknowledge":
                file_import_attempt.acknowledged = True
            else:
                file_import_attempt.acknowledged = False
            file_import_attempt.save()

        messages.success(
            request,
            f"File Import Attempt '{file_import_attempt}' has been "
            f"{'acknowledged' if file_import_attempt.acknowledged else 'unacknowledged'}",
        )
    return HttpResponseRedirect(file_import_attempt.get_absolute_url())


def changed_files_view(request):
    def do_reimport(post):
        ids = [int(fi_id[len(prefix) :]) for fi_id in post if fi_id.startswith(prefix)]
        if ids:
            file_importers = (
                FileImporter.objects.all().changed_files().filter(id__in=ids)
            )
        else:
            file_importers = FileImporter.objects.all().changed_files()

        if file_importers:
            for file_importer in file_importers:
                file_importer.reimport()

            messages.success(
                request,
                f"Successfully created {file_importers.count()} File Import Attempts ",
            )

            if file_importers.filter(
                status=FileImportAttempt.STATUSES.rejected.name
            ).exists():
                messages.error(
                    request,
                    f"One or more {FileImporter._meta.verbose_name_plural} "
                    "failed to reimport (no models were created)!",
                )
            elif file_importers.filter(
                status=FileImportAttempt.STATUSES.created_dirty.name
            ).exists():
                messages.warning(
                    request,
                    f"One or more {FileImporter._meta.verbose_name_plural} "
                    "had minor errors during their reimport process (but models "
                    "were still created)!",
                )
            else:
                messages.success(
                    request,
                    f"Successfully reimported all selected ({file_importers.count()}) "
                    f"{FileImporter._meta.verbose_name_plural}!",
                )
        else:
            messages.warning(request, f"No File Importers selected!")

    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        prefix = "file_importer_"

        foo_reimport = request.POST.get("submit_reimport", None)
        refresh_from_filesystem = request.POST.get(
            "submit_refresh_from_filesystem", None
        )
        if foo_reimport or refresh_from_filesystem:
            if foo_reimport:
                do_reimport(request.POST)
            else:
                FileImporter.objects.all().refresh_from_filesystem()
                messages.success(
                    request,
                    f"Successfully refreshed {FileImporter.objects.count()} importers from the filesystem",
                )

        return HttpResponseRedirect(request.path)

    changed_files = FileImporter.objects.all().changed_files()
    return render(
        request,
        "fileimportattempt_check_hashes.html",
        {
            "files_changed_since_import": changed_files,
            "last_hash_check": FileImporter.objects.order_by("created_on")
            .last()
            .hash_checked_on,
        },
    )
