# Generated by Django 5.1.2 on 2025-04-20 08:11

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0070_interviewfeedback_link'),
    ]

    operations = [
        migrations.CreateModel(
            name='InterviewScheduleAttempt',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('archived', models.BooleanField(default=False)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('candidate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scheduling_attempts', to='dashboard.candidate')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
