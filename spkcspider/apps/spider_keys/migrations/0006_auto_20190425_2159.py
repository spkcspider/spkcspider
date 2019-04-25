# Generated by Django 2.2 on 2019-04-25 21:59

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('spider_keys', '0005_remove_publickey_note'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AnchorKey',
        ),
        migrations.CreateModel(
            name='AnchorKey',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('signature', models.CharField(help_text='Signature of Identifier (hexadecimal-encoded)', max_length=1024)),
                ('key', models.OneToOneField(help_text='"Public Key"-Content for signing identifier. It is recommended to use different keys for signing and encryption.', on_delete=django.db.models.deletion.CASCADE, related_name='anchorkey', to='spider_keys.PublicKey')),
            ],
            options={
                'abstract': False,
                'default_permissions': [],
            },
        ),
        migrations.AddField(
            model_name='anchorserver',
            name='new_url',
            field=models.URLField(blank=True, help_text='Url to new anchor (in case this one is superseded)', max_length=400, null=True),
        ),
        migrations.AddField(
            model_name='anchorserver',
            name='old_urls',
            field=jsonfield.fields.JSONField(blank=True, default=list, help_text='Superseded anchor urls'),
        ),
    ]