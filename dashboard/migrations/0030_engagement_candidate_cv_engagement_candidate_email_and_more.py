# Generated by Django 5.1.2 on 2025-02-19 13:07

import django.db.models.deletion
import phonenumber_field.modelfields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0029_remove_engagement_unique_engagement_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='engagement',
            name='candidate_cv',
            field=models.FileField(blank=True, null=True, upload_to='engagement-candidate-cv'),
        ),
        migrations.AddField(
            model_name='engagement',
            name='candidate_email',
            field=models.EmailField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='candidate_name',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='candidate_phone',
            field=phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region='IN'),
        ),
        migrations.AlterField(
            model_name='engagement',
            name='candidate',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='engagements', to='dashboard.candidate'),
        ),
    ]
