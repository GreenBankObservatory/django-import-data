from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, FormView, UpdateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from .models import (
    ModelImportAttempt,
    FileImporter,
    FileImportAttempt,
    FileImporterBatch,
    RowData,
)
from .utils import humanize_timedelta


class CreateFromImportAttemptView(CreateView):
    def get_initial(self):
        self.model_import_attempt = get_object_or_404(
            ModelImportAttempt, id=self.kwargs["attempt_pk"]
        )
        return self.model_import_attempt.importee_field_data

    def form_valid(self, form):
        # if self.model_import_attempt.model_importer.models.exists():
        #     messages.error(self.request, f"Error! Already exists yo")
        #     return redirect(
        #         "modelimporter_detail", pk=self.model_import_attempt.model_importer.id
        #     )
        self.object = form.save()
        # self.object = form.save(commit=False)
        # self.object.row_data = self.model_import_attempt.model_importer.row_data
        # self.object.model_importers.set([self.model_import_attempt.model_importer])
        # form.save()
        try:
            model_import_attempt = ModelImportAttempt.objects.create_for_model(
                importee_field_data=form.cleaned_data,
                errors={},
                model_importer=self.model_import_attempt.model_importer,
                # TODO: Constant
                imported_by="Web UI",
                model=self.object,
                status=self.model_import_attempt.STATUSES.created_clean.db_value,
            )
        except ValueError as error:
            messages.error(self.request, f"Error! {error}")
        else:
            messages.success(
                self.request, f"Created Model Import Attempt: {model_import_attempt}"
            )
            messages.success(self.request, f"Created Model: {self.object}")

        self.object.model_import_attempt = model_import_attempt
        self.object.save()
        model_import_attempt.refresh_from_db()
        assert model_import_attempt.importee == self.object
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


def acknowledge_file_importer(request, pk):
    file_importer = get_object_or_404(FileImporter, id=pk)
    file_import_attempt = file_importer.latest_file_import_attempt
    if not file_import_attempt:
        messages.error(request, "No File Import Attempts; cannot acknowledge")
        return HttpResponseRedirect(file_importer.get_absolute_url())
    if request.method == "POST":
        acknowledge = request.POST.get("acknowledge", None)
        if acknowledge is None:
            messages.error(request, "Malformed request")
        else:
            if acknowledge == "Acknowledge":
                success = file_import_attempt.acknowledge()
                acknowledged_str = "acknowledged"
            else:
                success = file_import_attempt.unacknowledge()
                acknowledged_str = "unacknowledged"

        if success:
            messages.success(
                request,
                f"File Import Attempt '{file_import_attempt}' has been "
                f"{acknowledged_str}",
            )
        else:
            messages.warning(
                request,
                f"File Import Attempt '{file_import_attempt}' could not be acknowledged because it has already been deleted!",
            )
    return HttpResponseRedirect(file_importer.get_absolute_url())


def changed_files_view(request):
    def get_selected_file_importers(post):
        ids = [int(fi_id[len(prefix) :]) for fi_id in post if fi_id.startswith(prefix)]
        file_importers = FileImporter.objects.filter(id__in=ids)

        return file_importers

    def do_reimport(file_importers):
        if file_importers:
            errors = []
            for file_importer in file_importers:
                try:
                    file_importer.reimport()
                except Exception as error:
                    errors.append((file_importer, error))

            num_errors = len(errors)
            if not errors:
                messages.success(
                    request,
                    f"Successfully created {file_importers.count()} File Import Attempts ",
                )
                if file_importers.filter(
                    status=FileImportAttempt.STATUSES.rejected.db_value
                ).exists():
                    messages.error(
                        request,
                        f"One or more {FileImporter._meta.verbose_name_plural} "
                        "failed to reimport (no models were created)!",
                    )
                elif file_importers.filter(
                    status=FileImportAttempt.STATUSES.created_dirty.db_value
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
            elif num_errors == file_importers.count():
                messages.error(
                    request,
                    f"No file import attempts were successful (i.e. had fatal errors)!\n{errors}",
                )
            else:
                messages.warning(request, f"One or more fatal errors! \n{errors}")

    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        prefix = "file_importer_"

        submit_reimport = request.POST.get("submit_reimport", None)
        submit_reimport_all = request.POST.get("submit_reimport_all", None)
        submit_refresh_from_filesystem = request.POST.get(
            "submit_refresh_from_filesystem", None
        )
        submit_refresh_all_from_filesystem = request.POST.get(
            "submit_refresh_all_from_filesystem", None
        )

        if submit_reimport or submit_refresh_from_filesystem:
            file_importers = get_selected_file_importers(request.POST)

        if submit_reimport_all or submit_refresh_all_from_filesystem:
            file_importers = FileImporter.objects.all()

        if file_importers:
            if submit_reimport or submit_reimport_all:
                do_reimport(file_importers)

            if submit_refresh_from_filesystem or submit_refresh_all_from_filesystem:
                file_importers.refresh_from_filesystem()
                messages.success(
                    request,
                    f"Successfully refreshed {file_importers.count()} importers from the filesystem",
                )
        else:
            messages.warning(request, f"No File Importers selected!")

        return HttpResponseRedirect(request.path)

    changed_files = FileImporter.objects.all().changed_files()
    most_recent_check_time = (
        FileImporter.objects.order_by("hash_checked_on")
        .values_list("hash_checked_on", flat=True)
        .last()
    )

    time_since_last_check = timezone.now() - most_recent_check_time
    # TODO: Proper default in settings!
    max_time_since_last_check = getattr(
        settings, "MAX_TIME_SINCE_OLDEST_HASH_CHECK", timedelta(days=2)
    )
    if time_since_last_check > max_time_since_last_check:
        messages.warning(
            request,
            f"It has been {humanize_timedelta(time_since_last_check)} since the file hashes were "
            f"checked! Max allowed is {humanize_timedelta(max_time_since_last_check)}",
        )

    return render(
        request,
        "changed_files_dashboard.html",
        {
            "files_changed_since_import": changed_files,
            "most_recent_check_time": most_recent_check_time,
        },
    )
