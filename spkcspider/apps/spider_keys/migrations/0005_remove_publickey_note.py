# Generated by Django 2.2 on 2019-04-05 00:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('spider_keys', '0004_auto_20190221_2253'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='publickey',
            name='note',
        ),
    ]
