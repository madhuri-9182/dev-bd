# Generated by Django 5.1.2 on 2025-02-24 17:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_alter_user_email_verified_alter_user_phone_verified'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone_verified',
            field=models.BooleanField(default=True),
        ),
    ]
