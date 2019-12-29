# Generated by Django 3.0.1 on 2019-12-29 23:04

from django.db import migrations
import spkcspider.apps.spider_filets.models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0012_auto_20191229_2304'),
        ('spider_filets', '0013_auto_20191229_2304'),
    ]

    operations = [
        migrations.DeleteModel(
            name='FileFilet',
        ),
        migrations.DeleteModel(
            name='TextFilet',
        ),
        migrations.CreateModel(
            name='FileFilet',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=(spkcspider.apps.spider_filets.models.LicenseMixin, 'spider_base.datacontent'),
        ),
        migrations.CreateModel(
            name='TextFilet',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=(spkcspider.apps.spider_filets.models.LicenseMixin, 'spider_base.datacontent'),
        ),
    ]
