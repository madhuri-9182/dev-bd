# Generated by Django 5.1.2 on 2025-05-02 16:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0077_alter_interviewerpricing_experience_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='interview',
            name='is_billing_completed',
            field=models.BooleanField(default=False),
        ),
    ]
