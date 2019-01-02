Django Import Data
------------------

**THIS IS ALPHA SOFTWARE**


Motivation
==========

The problem: we have a bunch of Excel files, for example, that have columnar data we wish to create model instances from. However, this data is very messy, and we need some sane way to set up mappings between the data and our database.

This "messiness" comes in a few different forms.


Column names may change between source files
++++++++++++++++++++++++++++++++++++++++++++

For example, let's say you have a "name" column in your Excel files. However, between the various files this column appears under the headings "Name", "NAME", "Full Name", etc. *You* know that these all refer to the same thing, but you obviously need some way to map them all to the same "from field".

In ``django-import-data``, these various names for the same "from field" are referred to as aliases.


Columns may not map 1:1 to your database fields
+++++++++++++++++++++++++++++++++++++++++++++++

For example, let's say that you have "latitude" and "longitude" columns in your Excel files, but your database holds a single "location". The way this works in ``django-import-data`` is via the use of a "converter" function. In this example we might use ``lambda latitude, longitude: f"{latitude},{longitude}"`` as our converter -- it will merge these two columns into a single field.

Or, you might have a single "name" column in your Excel files, but "first_name" and "last_name" in your database. In this case you need to split these up: ``lambda name: name.split(" ")``


Columns may not contain clean data
++++++++++++++++++++++++++++++++++

For example, if we have a boolean column that represents ``None`` as either ``""`` or ``"n/a"``, depending on the file, we need a way to say that all of those mean the same thing. More broadly

If you're wondering why we don't just use Django forms for this: we are already using functions for our non-1:1 mappings, so we might as well do some cleaning while we're at it. There are other reasons, too; see below.


Why not Django forms?
=====================

Well, we actually *are* using Django forms under the hood. However, they simply aren't designed for these various use cases.

For example, while there is support for `n:1 relationships <https://docs.djangoproject.com/en/2.1/ref/forms/fields/#django.forms.MultiValueField>`_ it is *very* clunky in our use case.

And, from what I've been able to determine, there `isn't support at all for 1:n relationships <https://code.djangoproject.com/ticket/27>`_.

Further, while ``clean_foo`` are provided that make one-off clean functions easy to implement, this doesn't work for our use case, simply because it is so common to get "numbers" that can't actually be directly converted to a number in Python. This then forces us to create subclasses for every single affected field so we can override its ``to_python`` function. This ends up getting super messy.


Demo/Examples
=============

See the `demo Jupyter Notebook <example_project/django_import_data.ipynb>`_ for more information.
