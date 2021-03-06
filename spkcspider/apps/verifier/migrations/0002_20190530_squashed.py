# Generated by Django 2.2.1 on 2019-05-30 21:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):


    dependencies = [
        ('spider_verifier', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dataverificationtag',
            options={'permissions': [('can_verify', 'Can verify Data Tag?')]},
        ),
        migrations.AlterField(
            model_name='dataverificationtag',
            name='note',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='dataverificationtag',
            name='verification_state',
            field=models.CharField(choices=[('retrieve', 'retrieval pending'), ('pending', 'pending'), ('verified', 'verified'), ('invalid', 'invalid'), ('rejected', 'rejected')], default='retrieve', max_length=10),
        ),
        migrations.AddField(
            model_name='dataverificationtag',
            name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='spider_verifier.VerifySourceObject'),
        ),
        migrations.AlterField(
            model_name='dataverificationtag',
            name='verification_state',
            field=models.CharField(choices=[('pending', 'pending'), ('verified', 'verified'), ('invalid', 'invalid'), ('rejected', 'rejected')], default='pending', max_length=10),
        ),
        migrations.AddField(
            model_name='verifysourceobject',
            name='token',
            field=models.CharField(blank=True, max_length=126, null=True, unique=True),
        ),
    ]
