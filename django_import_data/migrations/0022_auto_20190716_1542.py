# Generated by Django 2.2.3 on 2019-07-16 19:42

import django.contrib.postgres.fields
from django.db import migrations
import django_import_data.mixins


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0021_remove_fileimporter_current_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileimportattempt',
            name='hash_when_imported',
            field=django_import_data.mixins.SensibleCharField(blank=True, max_length=40),
        ),
        migrations.AlterField(
            model_name='fileimportattempt',
            name='ignored_headers',
            field=django.contrib.postgres.fields.ArrayField(base_field=django_import_data.mixins.SensibleCharField(default=None, max_length=128), blank=True, help_text='Headers that were ignored during import', null=True, size=None),
        ),
        migrations.AlterField(
            model_name='fileimportattempt',
            name='imported_by',
            field=django_import_data.mixins.SensibleCharField(blank=True, default='', max_length=128),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='fileimportattempt',
            name='imported_from',
            field=django_import_data.mixins.SensibleCharField(default=None, help_text='Path to file that this was imported from', max_length=512),
        ),
        migrations.AlterField(
            model_name='fileimporter',
            name='file_path',
            field=django_import_data.mixins.SensibleCharField(default=None, help_text='Path to the file that this is linked to', max_length=512, unique=True),
        ),
        migrations.AlterField(
            model_name='fileimporter',
            name='hash_on_disk',
            field=django_import_data.mixins.SensibleCharField(blank=True, help_text='SHA-1 hash of the file on disk. If blank, the file is missing', max_length=40, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='fileimporter',
            name='importer_name',
            field=django_import_data.mixins.SensibleCharField(default=None, help_text='The name of the Importer to use', max_length=128),
        ),
        migrations.AlterField(
            model_name='fileimporterbatch',
            name='args',
            field=django.contrib.postgres.fields.ArrayField(base_field=django_import_data.mixins.SensibleCharField(default=None, max_length=256), size=None),
        ),
        migrations.AlterField(
            model_name='fileimporterbatch',
            name='command',
            field=django_import_data.mixins.SensibleCharField(default=None, max_length=64),
        ),
        migrations.AlterField(
            model_name='modelimportattempt',
            name='imported_by',
            field=django_import_data.mixins.SensibleCharField(default=None, max_length=128),
        ),
    ]