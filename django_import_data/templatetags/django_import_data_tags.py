import json as json_

from django import template

from django_import_data.models import (
    FileImportBatch,
    FileImporter,
    FileImportAttempt,
    ModelImportAttempt,
    RowData,
)

try:
    from pygments import highlight
    from pygments.lexers.data import JsonLexer
    from pygments.formatters import HtmlFormatter
except ImportError:
    USE_PYGMENTS = False
else:
    USE_PYGMENTS = True

register = template.Library()


@register.filter
def json(value):
    if not isinstance(value, str):
        value = json_.dumps(value, indent=2, sort_keys=True)

    if USE_PYGMENTS:
        return highlight(value, JsonLexer(), HtmlFormatter())
    return value


@register.filter
def qs_name(qs):
    try:
        try:
            return qs.model._meta.verbose_name
        except AttributeError:
            return qs.model.__name__
    except AttributeError:
        return None


@register.filter
def model_name(model):
    try:
        try:
            return model._meta.verbose_name
        except AttributeError:
            return model.__name__
    except AttributeError:
        return None


@register.filter
def gethash(thing):
    return abs(hash(thing))


@register.simple_tag
def get_verbose_name(form_map, field_name):
    return form_map.form_class.Meta.model._meta.get_field(field_name).verbose_name


@register.filter
def double_to_single_quotes(string):
    s = string.replace('"', "'")
    if not s:
        return "EMPTY ALIAS"
    return s


@register.filter
def spaces_to_underscores(string):
    return string.replace(" ", "_")


@register.inclusion_tag("breadcrumb/breadcrumb.html", takes_context=False)
def make_breadcrumb(item):
    if isinstance(item, FileImportBatch):
        context = {"file_import_batch": item}
        current = "file_import_batch"
    elif isinstance(item, FileImporter):
        context = {"file_importer": item}
        current = "file_importer"
    elif isinstance(item, FileImportAttempt):
        context = {
            "file_import_batch": item.file_import_batch,
            "file_importer": item.file_importer,
            "file_import_attempt": item,
        }
        current = "file_import_attempt"
    elif isinstance(item, RowData):
        context = {
            "file_import_batch": item.file_import_attempt.file_import_batch,
            "file_importer": item.file_import_attempt.file_importer,
            "file_import_attempt": item.file_import_attempt,
            "row_data": item,
        }
        current = "row_data"
    elif isinstance(item, ModelImportAttempt):
        context = {
            "file_import_batch": item.file_import_attempt.file_import_batch,
            "file_importer": item.file_import_attempt.file_importer,
            "file_import_attempt": item.file_import_attempt,
            "model_import_attempt": item,
            "row_data": item.row_data,
        }
        if item.importee:
            context["importee"] = item.importee
        current = "model_import_attempt"
    elif getattr(item, "model_import_attempt", None):
        context = {
            "file_import_batch": item.model_import_attempt.file_import_attempt.file_import_batch,
            "file_importer": item.model_import_attempt.file_import_attempt.file_importer,
            "file_import_attempt": item.model_import_attempt.file_import_attempt,
            "row_data": item.model_import_attempt.row_data,
            "model_import_attempt": item.model_import_attempt,
            "importee": item,
        }
        current = "importee"
    else:
        return {}

    context["current"] = current
    return context
