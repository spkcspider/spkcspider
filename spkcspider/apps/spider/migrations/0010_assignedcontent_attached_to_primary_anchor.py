# Generated by Django 2.1.7 on 2019-03-22 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0009_auto_20190317_1405'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignedcontent',
            name='attached_to_primary_anchor',
            field=models.BooleanField(default=False, editable=False, help_text='Content references primary anchor'),
        ),
    ]