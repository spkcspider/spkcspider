# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-11 16:06
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('spiderbroker', '0004_auto_20171103_0954'),
    ]

    operations = [
        migrations.RenameField(
            model_name='broker',
            old_name='content',
            new_name='content_info',
        ),
    ]
