# Generated by Django 2.2.2 on 2019-07-02 17:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0005_auto_20190619_1532'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileimportattempt',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'created_dirty'), (3, 'rejected')], db_index=True, default=0),
        ),
        migrations.AddField(
            model_name='fileimportbatch',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'created_dirty'), (3, 'rejected')], db_index=True, default=0),
        ),
        migrations.AddField(
            model_name='fileimporter',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'created_dirty'), (3, 'rejected')], db_index=True, default=0),
        ),
    ]
