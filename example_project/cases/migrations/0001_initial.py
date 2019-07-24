# Generated by Django 2.2.3 on 2019-07-24 20:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_import_data', '0022_auto_20190716_1542'),
    ]

    operations = [
        migrations.CreateModel(
            name='Structure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.CharField(max_length=256)),
                ('model_import_attempt', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='django_import_data.ModelImportAttempt')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=256)),
                ('phone', models.CharField(blank=True, max_length=256)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('city', models.CharField(blank=True, max_length=256)),
                ('street', models.CharField(blank=True, max_length=256)),
                ('zip', models.CharField(blank=True, max_length=256)),
                ('state', models.CharField(blank=True, max_length=256)),
                ('model_import_attempt', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='django_import_data.ModelImportAttempt')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Case',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('case_num', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('incomplete', 'incomplete'), ('complete', 'complete')], max_length=256)),
                ('type', models.CharField(blank=True, max_length=256)),
                ('subtype', models.PositiveIntegerField(blank=True)),
                ('applicant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='cases.Person')),
                ('model_import_attempt', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='django_import_data.ModelImportAttempt')),
                ('structure', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='cases.Structure')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
