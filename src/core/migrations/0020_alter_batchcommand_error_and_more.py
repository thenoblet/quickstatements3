# Generated by Django 5.0.9 on 2024-12-02 02:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_alter_batchcommand_operation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchcommand',
            name='error',
            field=models.TextField(blank=True, choices=[('op_not_implemented', 'Operation not implemented'), ('no_statements_property', 'No statements for given property'), ('no_statements_value', 'No statements with given value')], null=True),
        ),
        migrations.AlterField(
            model_name='batchcommand',
            name='operation',
            field=models.TextField(blank=True, choices=[('create_item', 'Create item'), ('create_property', 'Create property'), ('remove_statement_by_id', 'Remove statement by id'), ('remove_statement_by_value', 'Remove statement by value')], null=True),
        ),
    ]
