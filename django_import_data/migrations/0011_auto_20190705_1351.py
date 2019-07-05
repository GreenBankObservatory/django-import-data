# Generated by Django 2.2.2 on 2019-07-05 17:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0010_auto_20190705_1323'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='modelimportattempt',
            name='file_import_attempt',
        ),
        migrations.AddField(
            model_name='modelimporter',
            name='file_import_attempt',
            field=models.ForeignKey(blank=True, help_text='Reference to the FileImportAttempt this was created from', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='model_import_attempts', to='django_import_data.FileImportAttempt'),
        ),
    ]
