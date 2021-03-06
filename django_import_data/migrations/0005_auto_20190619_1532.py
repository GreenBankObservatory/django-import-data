# Generated by Django 2.2.2 on 2019-06-19 19:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_import_data', '0004_auto_20190619_1226'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modelimportattempt',
            name='is_active',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name='modelimportattempt',
            name='status',
            field=models.PositiveIntegerField(choices=[(0, 'pending'), (1, 'created_clean'), (2, 'created_dirty'), (3, 'rejected')], db_index=True, default=0),
        ),
    ]
