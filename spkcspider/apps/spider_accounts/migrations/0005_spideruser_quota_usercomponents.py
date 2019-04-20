# Generated by Django 2.2 on 2019-04-17 19:28

from django.db import migrations, models
import spkcspider.apps.spider_accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_accounts', '0004_auto_20190109_1505'),
    ]

    operations = [
        migrations.AddField(
            model_name='spideruser',
            name='quota_usercomponents',
            field=models.PositiveIntegerField(blank=True, default=spkcspider.apps.spider_accounts.models.default_quota_spider_user_components, help_text='Quota in units, null for no limit', null=True),
        ),
    ]