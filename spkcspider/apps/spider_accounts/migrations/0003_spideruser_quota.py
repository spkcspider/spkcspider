# Generated by Django 2.1.1 on 2018-09-22 22:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_accounts', '0001_initial'),
    ]
    replaces = [
        ('spider_accounts', '0002_auto_20180810_1433'),
    ]

    operations = [
        migrations.AddField(
            model_name='spideruser',
            name='quota',
            field=models.PositiveIntegerField(blank=True, default=None, help_text='Quota in Bytes, null to use standard', null=True),
        ),
    ]
