# Generated by Django 5.0.9 on 2024-11-08 19:52

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    BatchCommand = apps.get_model("core", "BatchCommand")
    for cmd in BatchCommand.objects.using(db_alias).all():
        user_summary = cmd.json.get("summary", None)
        if user_summary:
            cmd.user_summary = cmd.json.pop("summary", None)
            cmd.save()


def do_nothing(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_alter_batch_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="batchcommand",
            name="user_summary",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(forwards_func, do_nothing, elidable=True),
    ]