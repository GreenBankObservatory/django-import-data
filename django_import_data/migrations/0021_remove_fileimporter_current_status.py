# Generated by Django 2.2.3 on 2019-07-12 15:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0020_auto_20190712_1156'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fileimporter',
            name='current_status',
        ),
    ]
