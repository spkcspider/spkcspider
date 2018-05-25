# Generated by Django 2.0.5 on 2018-05-25 21:47

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields
import spkbspider.apps.spider.models
import spkbspider.apps.spider.protections


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AssignedProtection',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('data', jsonfield.fields.JSONField(default={})),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Protection',
            fields=[
                ('code', models.SlugField(max_length=10, primary_key=True, serialize=False)),
                ('ptype', models.CharField(default=spkbspider.apps.spider.protections.ProtectionType('\x01'), max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='UserComponent',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('name', models.SlugField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deletion_requested', models.DateTimeField(default=None, null=True)),
                ('protections', models.ManyToManyField(through='spiderucs.AssignedProtection', to='spiderucs.Protection')),
                ('user', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='UserContent',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deletion_requested', models.DateTimeField(default=None, null=True)),
                ('info', models.TextField(default=';', validators=[spkbspider.apps.spider.models.info_field_validator])),
                ('object_id', models.BigIntegerField(editable=False)),
                ('content_type', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
                ('usercomponent', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='contents', to='spiderucs.UserComponent')),
            ],
            options={
                'ordering': ['usercomponent', 'id'],
            },
        ),
        migrations.AddField(
            model_name='assignedprotection',
            name='protection',
            field=models.ForeignKey(editable=False, limit_choices_to=spkbspider.apps.spider.models.get_limit_choices_assigned_protection, on_delete=django.db.models.deletion.CASCADE, related_name='assigned', to='spiderucs.Protection'),
        ),
        migrations.AddField(
            model_name='assignedprotection',
            name='usercomponent',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='protected_by', to='spiderucs.UserComponent'),
        ),
        migrations.AddIndex(
            model_name='usercontent',
            index=models.Index(fields=['usercomponent'], name='spiderucs_u_usercom_68bf35_idx'),
        ),
        migrations.AddIndex(
            model_name='usercontent',
            index=models.Index(fields=['object_id'], name='spiderucs_u_object__8d4458_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='usercontent',
            unique_together={('content_type', 'object_id')},
        ),
        migrations.AddIndex(
            model_name='usercomponent',
            index=models.Index(fields=['user'], name='spiderucs_u_user_id_ee613d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='usercomponent',
            unique_together={('user', 'name')},
        ),
        migrations.AddIndex(
            model_name='assignedprotection',
            index=models.Index(fields=['usercomponent'], name='spiderucs_a_usercom_09421c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='assignedprotection',
            unique_together={('protection', 'usercomponent')},
        ),
    ]
