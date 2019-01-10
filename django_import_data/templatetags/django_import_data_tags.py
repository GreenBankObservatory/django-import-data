import json as json_

from django import template

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
