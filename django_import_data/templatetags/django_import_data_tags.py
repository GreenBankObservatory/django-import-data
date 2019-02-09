import json as json_

from django import template
from django.core.exceptions import FieldDoesNotExist


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
