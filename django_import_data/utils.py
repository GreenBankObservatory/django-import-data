from enum import Enum


class OrderedEnum(Enum):
    """Enum where order of members matters

    Order is used to determine greater/lesser than comparisons. For example,
    the first item declared is lesser than the last item declared"""

    def __gt__(self, other):
        _list = list(self.__class__)
        return _list.index(self) > _list.index(other)
