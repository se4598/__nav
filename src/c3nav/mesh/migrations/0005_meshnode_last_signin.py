# Generated by Django 4.2.1 on 2023-10-03 15:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mesh', '0004_relay_vs_src_node_and_remove_firmware'),
    ]

    operations = [
        migrations.AddField(
            model_name='meshnode',
            name='last_signin',
            field=models.DateTimeField(null=True, verbose_name='last signin'),
        ),
    ]
