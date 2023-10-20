# Generated by Django 4.2.1 on 2023-10-20 13:10

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    NodeMessage = apps.get_model("mesh", "NodeMessage")
    for msg in NodeMessage.objects.all():
        msg.message_type_new = msg.get_message_type_display()
        msg.save()


def backwards_func(apps, schema_editor):
    NodeMessage = apps.get_model("mesh", "NodeMessage")
    choices_lookup = {name: value for value, name in NodeMessage._meta.get_field("message_type").choices}
    for msg in NodeMessage.objects.all():
        msg.message_type = choices_lookup[msg.message_type_new]
        msg.save()


class Migration(migrations.Migration):
    dependencies = [
        ("mesh", "0006_rename_route_meshnode_uplink"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodemessage",
            name="message_type_new",
            field=models.CharField(
                choices=[
                    ("NOOP", "Noop"),
                    ("ECHO_REQUEST", "Echo Request"),
                    ("ECHO_RESPONSE", "Echo Response"),
                    ("MESH_SIGNIN", "Mesh Signin"),
                    ("MESH_LAYER_ANNOUNCE", "Mesh Layer Announce"),
                    ("MESH_ADD_DESTINATIONS", "Mesh Add Destinations"),
                    ("MESH_REMOVE_DESTINATIONS", "Mesh Remove Destinations"),
                    ("MESH_ROUTE_REQUEST", "Mesh Route Request"),
                    ("MESH_ROUTE_RESPONSE", "Mesh Route Response"),
                    ("MESH_ROUTE_TRACE", "Mesh Route Trace"),
                    ("MESH_ROUTING_FAILED", "Mesh Routing Failed"),
                    ("CONFIG_DUMP", "Config Dump"),
                    ("CONFIG_HARDWARE", "Config Hardware"),
                    ("CONFIG_BOARD", "Config Board"),
                    ("CONFIG_FIRMWARE", "Config Firmware"),
                    ("CONFIG_UPLINK", "Config Uplink"),
                    ("CONFIG_POSITION", "Config Position"),
                    ("OTA_STATUS", "Ota Status"),
                    ("OTA_REQUEST_STATUS", "Ota Request Status"),
                    ("OTA_START", "Ota Start"),
                    ("OTA_URL", "Ota Url"),
                    ("OTA_FRAGMENT", "Ota Fragment"),
                    ("OTA_REQUEST_FRAGMENT", "Ota Request Fragment"),
                    ("OTA_APPLY", "Ota Apply"),
                    ("OTA_REBOOT", "Ota Reboot"),
                    ("LOCATE_REQUEST_RANGE", "Locate Request Range"),
                    ("LOCATE_RANGE_RESULTS", "Locate Range Results"),
                ],
                db_index=True,
                max_length=24,
                null=True,
                verbose_name="message type",
            ),
        ),
        migrations.AlterField(
            model_name="nodemessage",
            name="message_type",
            field=models.SmallIntegerField(
                choices=[
                    (0, "NOOP"),
                    (1, "ECHO_REQUEST"),
                    (2, "ECHO_RESPONSE"),
                    (3, "MESH_SIGNIN"),
                    (4, "MESH_LAYER_ANNOUNCE"),
                    (5, "MESH_ADD_DESTINATIONS"),
                    (6, "MESH_REMOVE_DESTINATIONS"),
                    (7, "MESH_ROUTE_REQUEST"),
                    (8, "MESH_ROUTE_RESPONSE"),
                    (9, "MESH_ROUTE_TRACE"),
                    (10, "MESH_ROUTING_FAILED"),
                    (16, "CONFIG_DUMP"),
                    (17, "CONFIG_HARDWARE"),
                    (18, "CONFIG_BOARD"),
                    (19, "CONFIG_FIRMWARE"),
                    (20, "CONFIG_UPLINK"),
                    (21, "CONFIG_POSITION"),
                    (32, "OTA_STATUS"),
                    (33, "OTA_REQUEST_STATUS"),
                    (34, "OTA_START"),
                    (35, "OTA_URL"),
                    (36, "OTA_FRAGMENT"),
                    (37, "OTA_REQUEST_FRAGMENT"),
                    (38, "OTA_APPLY"),
                    (39, "OTA_REBOOT"),
                    (48, "LOCATE_REQUEST_RANGE"),
                    (49, "LOCATE_RANGE_RESULTS"),
                ],
                db_index=True,
                verbose_name="message type",
            ),
        ),
        migrations.RunPython(forwards_func, backwards_func),
        migrations.RemoveField(
            model_name="nodemessage",
            name="message_type",
        ),
        migrations.AlterField(
            model_name="nodemessage",
            name="message_type_new",
            field=models.CharField(
                choices=[
                    ("NOOP", "Noop"),
                    ("ECHO_REQUEST", "Echo Request"),
                    ("ECHO_RESPONSE", "Echo Response"),
                    ("MESH_SIGNIN", "Mesh Signin"),
                    ("MESH_LAYER_ANNOUNCE", "Mesh Layer Announce"),
                    ("MESH_ADD_DESTINATIONS", "Mesh Add Destinations"),
                    ("MESH_REMOVE_DESTINATIONS", "Mesh Remove Destinations"),
                    ("MESH_ROUTE_REQUEST", "Mesh Route Request"),
                    ("MESH_ROUTE_RESPONSE", "Mesh Route Response"),
                    ("MESH_ROUTE_TRACE", "Mesh Route Trace"),
                    ("MESH_ROUTING_FAILED", "Mesh Routing Failed"),
                    ("CONFIG_DUMP", "Config Dump"),
                    ("CONFIG_HARDWARE", "Config Hardware"),
                    ("CONFIG_BOARD", "Config Board"),
                    ("CONFIG_FIRMWARE", "Config Firmware"),
                    ("CONFIG_UPLINK", "Config Uplink"),
                    ("CONFIG_POSITION", "Config Position"),
                    ("OTA_STATUS", "Ota Status"),
                    ("OTA_REQUEST_STATUS", "Ota Request Status"),
                    ("OTA_START", "Ota Start"),
                    ("OTA_URL", "Ota Url"),
                    ("OTA_FRAGMENT", "Ota Fragment"),
                    ("OTA_REQUEST_FRAGMENT", "Ota Request Fragment"),
                    ("OTA_APPLY", "Ota Apply"),
                    ("OTA_REBOOT", "Ota Reboot"),
                    ("LOCATE_REQUEST_RANGE", "Locate Request Range"),
                    ("LOCATE_RANGE_RESULTS", "Locate Range Results"),
                ],
                db_index=True,
                max_length=24,
                verbose_name="message type",
            ),
        ),
        migrations.RenameField(
            model_name="nodemessage",
            old_name="message_type_new",
            new_name="message_type",
        ),
    ]
