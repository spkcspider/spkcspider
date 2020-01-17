# Generated by Django 3.0.1 on 2019-12-30 13:00

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields
import spkcspider.apps.spider.models.content_extended
import spkcspider.constants.protections


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0009_auto_20190929_2117'),
    ]

    operations = [
        migrations.CreateModel(
            name='M2MTravelProtContent',
            fields=[
                ('id', models.BigAutoField(editable=False,
                                           primary_key=True, serialize=False)),
                ('source', models.ForeignKey(limit_choices_to=models.Q(('ctype__name', 'TravelProtection'), ('ctype__name', 'SelfProtection'),
                                                                       _connector='OR'), on_delete=django.db.models.deletion.CASCADE, related_name='+', to='spider_base.AssignedContent')),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='+', to='spider_base.AssignedContent')),
            ],
        ),
        migrations.CreateModel(
            name='M2MTravelProtComponent',
            fields=[
                ('id', models.BigAutoField(editable=False,
                                           primary_key=True, serialize=False)),
                ('source', models.ForeignKey(limit_choices_to=models.Q(('ctype__name', 'TravelProtection'), ('ctype__name', 'SelfProtection'),
                                                                       _connector='OR'), on_delete=django.db.models.deletion.CASCADE, related_name='+', to='spider_base.AssignedContent')),
                ('target', models.ForeignKey(limit_choices_to={
                 'strength__lt': 10}, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='spider_base.UserComponent')),
            ],
        ),
        migrations.CreateModel(
            name='AttachedBlob',
            fields=[
                ('id', models.BigAutoField(editable=False,
                                           primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', max_length=50)),
                ('unique', models.BooleanField(blank=True, default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('blob', models.BinaryField(blank=True, default=b'', editable=True)),
            ],
        ),
        migrations.CreateModel(
            name='AttachedCounter',
            fields=[
                ('id', models.BigAutoField(editable=False,
                                           primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', max_length=50)),
                ('unique', models.BooleanField(blank=True, default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('counter', models.BigIntegerField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AttachedFile',
            fields=[
                ('id', models.BigAutoField(editable=False,
                                           primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', max_length=50)),
                ('unique', models.BooleanField(blank=True, default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(upload_to=spkcspider.apps.spider.models.content_extended.get_file_path)),
            ],
        ),
        migrations.CreateModel(
            name='AttachedTimeSpan',
            fields=[
                ('id', models.BigAutoField(editable=False,
                                           primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', max_length=50)),
                ('unique', models.BooleanField(blank=True, default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('start', models.DateTimeField()),
                ('stop', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='DataContent',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('quota_data', jsonfield.fields.JSONField(default=dict, blank=True)),
                ('free_data', jsonfield.fields.JSONField(default=dict, blank=True)),
            ],
            options={
                'abstract': False,
                'default_permissions': (),
            },
            managers=[
                ('objects', spkcspider.apps.spider.models.content_extended.DataContentManager()),
            ],
        ),
        migrations.AlterField(
            model_name='assignedprotection',
            name='state',
            field=models.CharField(choices=[(spkcspider.constants.protections.ProtectionStateType['disabled'], 'disabled'), (spkcspider.constants.protections.ProtectionStateType['enabled'], 'enabled'), (spkcspider.constants.protections.ProtectionStateType['instant_fail'], 'instant fail')], default=spkcspider.constants.protections.ProtectionStateType['enabled'], help_text='State of the protection.', max_length=1),
        ),
        migrations.AlterUniqueTogether(
            name='assignedcontent',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='assignedcontent',
            name='protect_components',
            field=models.ManyToManyField(blank=True, related_name='travel_protected',
                                         through='spider_base.M2MTravelProtComponent', through_fields=("source", "target"), to='spider_base.UserComponent'),
        ),
        migrations.AddField(
            model_name='assignedcontent',
            name='protect_contents',
            field=models.ManyToManyField(blank=True, related_name='travel_protected',
                                         through='spider_base.M2MTravelProtContent', through_fields=("source", "target"), to='spider_base.AssignedContent'),
        ),
        migrations.AddField(
            model_name='datacontent',
            name='associated',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='spider_base.AssignedContent'),
        ),
        migrations.AddField(
            model_name='attachedtimespan',
            name='content',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='attachedtimespans', to='spider_base.AssignedContent'),
        ),
        migrations.AddField(
            model_name='attachedfile',
            name='content',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='attachedfiles', to='spider_base.AssignedContent'),
        ),
        migrations.AddField(
            model_name='attachedcounter',
            name='content',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='attachedcounters', to='spider_base.AssignedContent'),
        ),
        migrations.AddField(
            model_name='attachedblob',
            name='content',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='attachedblobs', to='spider_base.AssignedContent'),
        ),
        migrations.RemoveField(
            model_name='assignedcontent',
            name='content_type',
        ),
        migrations.AddConstraint(
            model_name='attachedblob',
            constraint=models.UniqueConstraint(condition=models.Q(
                unique=True), fields=('content', 'name'), name='attachedblob_unique'),
        ),
        migrations.AddConstraint(
            model_name='attachedcounter',
            constraint=models.UniqueConstraint(condition=models.Q(unique=True), fields=(
                'content', 'name'), name='attachedcounter_unique'),
        ),
        migrations.AddConstraint(
            model_name='attachedfile',
            constraint=models.UniqueConstraint(condition=models.Q(
                unique=True), fields=('content', 'name'), name='attachedfile_unique'),
        ),
        migrations.AddConstraint(
            model_name='attachedtimespan',
            constraint=models.UniqueConstraint(condition=models.Q(unique=True), fields=(
                'content', 'name'), name='attachedtimespan_unique'),
        ),
        migrations.AddConstraint(
            model_name='attachedtimespan',
            constraint=models.CheckConstraint(check=models.Q(('start__lte', django.db.models.expressions.F('stop')), ('start__isnull', True), ('stop__isnull', True), _connector='OR'), name='attachedtimespan_order'),
        ),
        migrations.AddConstraint(
            model_name='attachedtimespan',
            constraint=models.CheckConstraint(check=models.Q(('start__isnull', False), ('stop__isnull', False), _connector='OR'), name='attachedtimespan_exist'),
        ),
    ]
