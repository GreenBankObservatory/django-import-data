from enum import Enum

from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.gis.geos import GEOSGeometry


class OrderedEnum(Enum):
    """Enum where order of members matters

    Order is used to determine greater/lesser than comparisons. For example,
    the first item declared is lesser than the last item declared"""

    def __gt__(self, other):
        _list = list(self.__class__)
        return _list.index(self) > _list.index(other)


class DjangoErrorJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        # GEOSGeometry isn't an error, but still should be serialized as a string
        if isinstance(obj, (Exception, GEOSGeometry)):
            return repr(obj)

        return super().default(obj)
