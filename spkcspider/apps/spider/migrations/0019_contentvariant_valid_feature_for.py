# Generated by Django 2.2.1 on 2019-05-08 20:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0018_auto_20190505_1336'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentvariant',
            name='valid_feature_for',
            field=models.ManyToManyField(blank=True, related_name='valid_features', to='spider_base.ContentVariant'),
        ),
    ]
