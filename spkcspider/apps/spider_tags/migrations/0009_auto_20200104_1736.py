# Generated by Django 3.0.2 on 2020-01-04 17:36

from django.db import migrations


def move_to_datacontent(apps, schema_editor):
    AssignedContent = apps.get_model("spider_base", "AssignedContent")
    UserTagLayout = apps.get_model("spider_tags", "UserTagLayout")
    TagLayout = apps.get_model("spider_tags", "TagLayout")
    SpiderTag = apps.get_model("spider_tags", "SpiderTag")
    DataContent = apps.get_model("spider_base", "DataContent")

    for a in AssignedContent.objects.filter(
        ctype__code=UserTagLayout._meta.model_name
    ):
        d = DataContent(associated=a)
        layout = TagLayout.objects.get(usertag__id=a.object_id)
        layout.usertag = None
        layout.save()
        d.free_data["tmp_layout_id"] = layout.id
        d.save()

    for a in AssignedContent.objects.filter(
        ctype__code=SpiderTag._meta.model_name
    ):
        content = SpiderTag.objects.get(id=a.object_id)
        content.associated = a
        content.save()


class Migration(migrations.Migration):

    dependencies = [
        ('spider_tags', '0008_auto_20200104_1735'),
    ]

    run_before = [
        ('spider_base', '0012_auto_20191230_1305'),
    ]

    operations = [
        migrations.RunPython(move_to_datacontent),
    ]
