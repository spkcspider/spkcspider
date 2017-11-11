# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-03 06:43
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.SPIDERPK_USERCOMPONENT_MODEL),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Broker',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('brokertype', models.SlugField(choices=[('oauth', 'OAUTH'), ('jwt', 'JWT')], max_length=10)),
                ('brokerdata', jsonfield.fields.JSONField(default={})),
                ('url', models.URLField(default='', max_length=300)),
                ('extra', jsonfield.fields.JSONField(default={})),
                ('protected_by', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.SPIDERPK_USERCOMPONENT_MODEL)),
                ('user', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'swappable': 'SPIDERBROKER_BROKER_MODEL',
            },
        ),
    ]