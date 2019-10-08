from enum import Enum, EnumMeta
import hashlib
import os
import re
from subprocess import CalledProcessError, check_output

from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.gis.geos import Point


class FancyEnumMeta(EnumMeta):
    def __getitem__(cls, key):
        if isinstance(key, int):
            return list(cls)[key]
        try:
            return getattr(cls, key)
        except AttributeError as error:
            keys = [item.name for item in cls]
            raise KeyError(f"Invalid key '{key}'. Choices are: {keys}")


class OrderedEnum(Enum, metaclass=FancyEnumMeta):
    """Enum where order of members matters

    Order is used to determine greater/lesser than comparisons. For example,
    the first item declared is lesser than the last item declared"""

    def __gt__(self, other):
        _list = list(self.__class__)
        return _list.index(self) > _list.index(other)

    @property
    def db_value(self):
        _list = list(self.__class__)
        return _list.index(self)

    @classmethod
    def as_choices(cls):
        return tuple((index, status.name) for index, status in enumerate(cls))

    @classmethod
    def as_filter_choices(cls):
        return tuple((index, status.value) for index, status in enumerate(cls))


class DjangoErrorJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        from django.contrib.gis.db.backends.postgis.models import PostGISSpatialRefSys

        if isinstance(obj, Exception):
            return repr(obj)
        # GEOSGeometry isn't an error, but still should be serialized as a string
        if isinstance(obj, Point):
            return repr(obj.coords)
        if isinstance(obj, PostGISSpatialRefSys):
            return obj.srid

        return super().default(obj)


def to_fancy_str(iterable, quote=False):
    iterable_length = len(iterable)
    if quote:
        stringifier = lambda x: repr(str(x))
    else:
        stringifier = str
    if iterable_length == 0:
        return ""
    elif iterable_length == 1:
        return stringifier(list(iterable)[0])
    elif iterable_length == 2:
        return " and ".join([stringifier(item) for item in iterable])
    else:
        l = [stringifier(item) for item in iterable]
        return f"{', '.join(l[:-1])}, and {l[-1]}"


def hash_file(path):
    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        while True:
            data = file.read(65536)
            if data:
                sha1.update(data)
            else:
                break
    return sha1.hexdigest()


# Modified from: http://stackoverflow.com/a/323910/1883424
def itemAndNext(iterable):
    """Generator to yield an item and the next item.

    Args:
        iterable: An iterable

    Returns:
        tuple: A tuple of the current item and the next item"""

    iterator = iter(iterable)
    item = next(iterator)
    for next_item in iterator:
        yield (item, next_item)
        item = next_item
    yield (item, None)


def make_list_of_ranges_from_nums(nums, prefix=None):
    """Parse a list of numbers into a list of ranges.

    This is a helper function for get_str_from_nums(), and does all of the
    hard work of creating a list of ranges from a list of nums.

    Args:
        nums: A collection of numbers

    Returns:
        list: A list of length-2 tuples, with each tuple representing the
        min/max (inclusive) of a range.
    """

    # Make sure they are sorted
    if not nums:
        return []
    nums = sorted(nums)
    ranges = []
    # The first range_start will be the first element of nums
    range_start = None
    for num, next_num in itemAndNext(nums):
        num = int(num)
        next_num = int(next_num) if next_num else None
        if not range_start:
            range_start = num

        if next_num is None or num + 1 != next_num:
            if prefix is not None:
                ranges.append((f"{prefix}{range_start}", f"{prefix}{num}"))
            else:
                ranges.append((range_start, num))
            range_start = None

    return ranges


def get_str_from_nums(nums, join_str=", ", range_str="–", prefix=None):
    """Create a string representation of a series of number ranges given a
    list of numbers.

    Remember that the user's input string could be something ridiculous,
    such as '5-7,1-6', which yields [1,2,3,4,5,6,7] and
    should be represented as '1-7'.

    Args:
        nums: A collection of numbers
        join_str: An optional argument representing the string that will be
        used to join the series of ranges together

    Returns:
        str: String representation of a series of number ranges
    """

    ranges_list = make_list_of_ranges_from_nums(nums, prefix=prefix)
    item_list = []

    for range_ in ranges_list:
        assert len(range_) == 2
        # Eliminate duplicates
        if range_[0] == range_[1]:
            item_list.append(str(range_[0]))
        # Use join_str if the second number is only one higher than the first
        elif range_[1] - range_[0] == 1:
            item_list.append(str(range_[0]) + join_str + str(range_[1]))
        # Otherwise, use the range_str to represent a range of ints
        else:
            item_list.append(str(range_[0]) + range_str + str(range_[1]))

    return join_str.join(item_list)


# Adapted from: https://gist.github.com/thatalextaylor/7408395
def humanize_timedelta(td):
    seconds = td.total_seconds()
    sign_string = "-" if seconds < 0 else ""
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{sign_string}{days}d{hours}h{minutes}m{seconds}s"
    elif hours > 0:
        return f"{sign_string}{hours}h{minutes}m{seconds}s"
    elif minutes > 0:
        return f"{sign_string}{minutes}m{seconds}s"
    else:
        return f"{sign_string}{seconds}s"


def determine_files_to_process_slow(paths, pattern=None):
    """Find all files in given paths that match given pattern; sort and return"""
    if isinstance(paths, str):
        paths = [paths]
    if pattern:
        pattern = re.compile(pattern)
    matched_files = []
    for path in paths:
        if os.path.isfile(path):
            matched_files.append(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                matched_files.extend(
                    [
                        os.path.join(path, root, file)
                        for file in files
                        if not pattern or pattern.match(file)
                    ]
                )
        else:
            raise ValueError(f"Given path {path!r} is not a directory or file!")

    return sorted(matched_files)


# Roughly 2.5x faster!
def determine_files_to_process(paths, pattern=None, maxdepth=2):
    if isinstance(paths, str):
        paths = [paths]
    cmd = ["find", *paths]
    if maxdepth is not None:
        cmd += ["-maxdepth", "2"]
    cmd += ["-type", "f"]
    if pattern:
        cmd += ["-regextype", "posix-extended", "-regex", pattern]

    try:
        return sorted(check_output(cmd).decode("utf-8").splitlines())
    except CalledProcessError as error:
        print(
            "WARNING: Falling back to determine_files_to_process_slow due to error in "
            f"determine_files_to_process:\n{error}"
        )
        return determine_files_to_process_slow(paths, pattern)
