# Generated by Django 2.1.5 on 2019-02-07 23:21

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0003_rowdata_headers'),
    ]

    operations = [
        migrations.AddField(
            model_name='rowdata',
            name='errors',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict, null=True),
        ),
    ]
