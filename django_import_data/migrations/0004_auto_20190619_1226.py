# Generated by Django 2.2.2 on 2019-06-19 16:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0003_auto_20190618_1629'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modelimportattempt',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'Pending'), (1, 'Imported: No Errors'), (2, 'Imported: Some Errors'), (3, 'Rejected: Fatal Errors')], default=0),
        ),
    ]
