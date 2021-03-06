# Generated by Django 2.2.3 on 2019-07-12 15:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0019_rowdata_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fileimportattempt',
            name='acknowledged',
        ),
        migrations.AddField(
            model_name='fileimportattempt',
            name='current_status',
            field=models.PositiveIntegerField(choices=[(0, 'deleted'), (1, 'acknowledged'), (2, 'active')], db_index=True, default=2),
        ),
        migrations.AddField(
            model_name='fileimporter',
            name='current_status',
            field=models.PositiveIntegerField(choices=[(0, 'deleted'), (1, 'acknowledged'), (2, 'active')], db_index=True, default=2),
        ),
        migrations.AlterField(
            model_name='fileimportattempt',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'empty'), (3, 'created_dirty'), (4, 'rejected')], db_index=True, default=0),
        ),
        migrations.AlterField(
            model_name='fileimporter',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'empty'), (3, 'created_dirty'), (4, 'rejected')], db_index=True, default=0),
        ),
        migrations.AlterField(
            model_name='fileimporterbatch',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'empty'), (3, 'created_dirty'), (4, 'rejected')], db_index=True, default=0),
        ),
        migrations.AlterField(
            model_name='modelimportattempt',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'empty'), (3, 'created_dirty'), (4, 'rejected')], db_index=True, default=0),
        ),
        migrations.AlterField(
            model_name='modelimporter',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'empty'), (3, 'created_dirty'), (4, 'rejected')], db_index=True, default=0),
        ),
        migrations.AlterField(
            model_name='rowdata',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'empty'), (3, 'created_dirty'), (4, 'rejected')], db_index=True, default=0),
        ),
    ]
