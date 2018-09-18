# Generated by Django 2.1 on 2018-09-18 11:38

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import spkcspider.apps.spider.models.contents
import spkcspider.apps.spider.models.protections


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0002_auto_20180903_0114'),
    ]

    operations = [
        migrations.CreateModel(
            name='TravelProtection',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('active', models.BooleanField(default=False)),
                ('start', models.DateTimeField(default=spkcspider.apps.spider.models.contents.default_start)),
                ('stop', models.DateTimeField(default=spkcspider.apps.spider.models.contents.default_stop, null=True)),
                ('self_protection', models.BooleanField(default=True, help_text='\n    Disallows user to disable travel protection if active.\n    Can be used in connection with "secret" to allow unlocking via secret\n')),
                ('login_protection', models.CharField(choices=[('a', 'No Login protection')], default='a', help_text='\n    No Login Protection: normal, default\n    Fake Login: fake login and index (experimental)\n    Wipe: Wipe protected content,\n    except they are protected by a deletion period\n    Wipe User: destroy user on login\n\n\n    <div>\n        Danger: every option other than: "No Login Protection" can screw you.\n        "Fake Login" can trap you in a parallel reality\n    </div>\n', max_length=10)),
                ('secret', models.SlugField(default='', max_length=120)),
            ],
            options={
                'abstract': False,
                'default_permissions': [],
            },
        ),
        migrations.AlterField(
            model_name='assignedprotection',
            name='protection',
            field=models.ForeignKey(limit_choices_to=spkcspider.apps.spider.models.protections.get_limit_choices_assigned_protection, on_delete=django.db.models.deletion.CASCADE, related_name='assigned', to='spider_base.Protection'),
        ),
        migrations.AlterField(
            model_name='usercomponent',
            name='deletion_requested',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='usercomponent',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='travelprotection',
            name='disallow',
            field=models.ManyToManyField(limit_choices_to=spkcspider.apps.spider.models.contents.own_components, related_name='travel_protected', to='spider_base.UserComponent'),
        ),
    ]