import traceback

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer, JsonWebsocketConsumer
from django.utils import timezone

from c3nav.mesh.utils import get_mesh_comm_group
from c3nav.mesh import messages
from c3nav.mesh.messages import MeshMessage, BROADCAST_ADDRESS
from c3nav.mesh.models import MeshNode, NodeMessage


# noinspection PyAttributeOutsideInit
class MeshConsumer(WebsocketConsumer):
    def connect(self):
        # todo: auth
        self.uplink_node = None
        self.log_text(None, "new mesh websocket connection")
        self.dst_nodes = set()
        self.accept()

    def disconnect(self, close_code):
        self.log_text(self.uplink_node, "mesh websocket disconnected")
        if self.uplink_node is not None:
            # leave broadcast group
            async_to_sync(self.channel_layer.group_add)(get_mesh_comm_group(BROADCAST_ADDRESS), self.channel_name)

            # remove all other destinations
            self.remove_dst_nodes(self.dst_nodes)

    def send_msg(self, msg, sender=None):
        # print("sending", msg)
        # self.log_text(msg.dst, "sending %s" % msg)
        self.send(bytes_data=msg.encode())
        async_to_sync(self.channel_layer.group_send)("mesh_msg_sent", {
            "type": "mesh.msg_sent",
            "timestamp": timezone.now().strftime("%d.%m.%y %H:%M:%S.%f"),
            "channel": self.channel_name,
            "sender": sender,
            "uplink": self.uplink_node.address if self.uplink_node else None,
            "recipient": msg.dst,
            #"msg": msg.tojson(),  # not doing this part for privacy reasons
        })

    def receive(self, text_data=None, bytes_data=None):
        if bytes_data is None:
            return
        try:
            msg = messages.MeshMessage.decode(bytes_data)
        except Exception:
            traceback.print_exc()
            return

        if msg.dst != messages.ROOT_ADDRESS and msg.dst != messages.PARENT_ADDRESS:
            print('Received message for forwarding:', msg)
            # todo: this message isn't for us, forward it
            return

        #print('Received message:', msg)

        src_node, created = MeshNode.objects.get_or_create(address=msg.src)

        if isinstance(msg, messages.MeshSigninMessage):
            self.uplink_node = src_node
            # log message, since we will not log it further down
            self.log_received_message(src_node, msg)

            # inform signed in uplink node about its layer
            self.send_msg(messages.MeshLayerAnnounceMessage(
                src=messages.ROOT_ADDRESS,
                dst=msg.src,
                layer=messages.NO_LAYER
            ))

            # add signed in uplink node to broadcast group
            async_to_sync(self.channel_layer.group_add)('mesh_broadcast', self.channel_name)

            # kick out other consumers talking to the same uplink
            async_to_sync(self.channel_layer.group_send)(get_mesh_comm_group(msg.src), {
                "type": "mesh.uplink_consumer",
                "name": self.channel_name,
            })

            # add this node as a destination that this uplink handles (duh)
            self.add_dst_nodes(nodes=(src_node, ))

            return

        if self.uplink_node is None:
            print('Expected sign-in message, but got a different one!')
            self.close()
            return

        self.log_received_message(src_node, msg)

        if isinstance(msg, messages.MeshAddDestinationsMessage):
            self.add_dst_nodes(addresses=msg.addresses)

        if isinstance(msg, messages.MeshRemoveDestinationsMessage):
            self.remove_dst_nodes(addresses=msg.addresses)

    def mesh_uplink_consumer(self, data):
        # message handler: if we are not the given uplink, leave this group
        if data["name"] != self.channel_name:
            self.log_text(self.uplink_node, "shutting down, uplink now served by new consumer")
            self.close()

    def mesh_dst_node_uplink(self, data):
        # message handler: if we are not the given uplink, leave this group
        if data["uplink"] != self.uplink_node.address:
            self.log_text(data["address"], "node now served by new consumer")
            self.remove_dst_nodes((data["address"], ))

    def mesh_send(self, data):
        print("mesh_send", data)
        self.send_msg(MeshMessage.fromjson(data["msg"]), data["sender"])

    def log_received_message(self, src_node: MeshNode, msg: messages.MeshMessage):
        as_json = msg.tojson()
        async_to_sync(self.channel_layer.group_send)("mesh_msg_received", {
            "type": "mesh.msg_received",
            "timestamp": timezone.now().strftime("%d.%m.%y %H:%M:%S.%f"),
            "channel": self.channel_name,
            "uplink": self.uplink_node.address if self.uplink_node else None,
            "msg": as_json,
        })
        NodeMessage.objects.create(
            uplink_node=self.uplink_node,
            src_node=src_node,
            message_type=msg.msg_id,
            data=as_json,
        )

    def log_text(self, address, text):
        address = getattr(address, 'address', address)
        async_to_sync(self.channel_layer.group_send)("mesh_log", {
            "type": "mesh.log_entry",
            "timestamp": timezone.now().strftime("%d.%m.%y %H:%M:%S.%f"),
            "channel": self.channel_name,
            "uplink": self.uplink_node.address if self.uplink_node else None,
            "node": address,
            "text": text,
        })

    def add_dst_nodes(self, nodes=None, addresses=None):
        nodes = list(nodes) if nodes else []
        addresses = set(addresses) if addresses else set()

        node_addresses = set(node.address for node in nodes)
        missing_addresses = addresses - set(node.address for node in nodes)

        if missing_addresses:
            MeshNode.objects.bulk_create(
                [MeshNode(address=address) for address in missing_addresses],
                ignore_conflicts=True
            )

        addresses |= node_addresses
        addresses |= missing_addresses

        for address in addresses:
            self.log_text(address, "destination added")

            # create group name for this address
            group = get_mesh_comm_group(address)

            # if we aren't handling this address yet, join the group
            if address not in self.dst_nodes:
                async_to_sync(self.channel_layer.group_add)(group, self.channel_name)
                self.dst_nodes.add(address)

            # tell other consumers to leave the group
            async_to_sync(self.channel_layer.group_send)(group, {
                "type": "mesh.dst_node_uplink",
                "node": address,
                "uplink": self.uplink_node.address
            })

            # tell the node to dump its current information
            self.send_msg(
                messages.ConfigDumpMessage(
                    src=messages.ROOT_ADDRESS,
                    dst=address,
                )
            )

        # add the stuff to the db as well
        MeshNode.objects.filter(address__in=addresses).update(
            uplink_id=self.uplink_node.address,
            last_signin=timezone.now(),
        )

    def remove_dst_nodes(self, addresses):
        for address in tuple(addresses):
            self.log_text(address, "destination removed")

            # create group name for this address
            group = get_mesh_comm_group(address)

            # leave the group
            if address in self.dst_nodes:
                async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)
                self.dst_nodes.discard(address)

        # add the stuff to the db as well
        # todo: shouldn't do this because of race condition?
        MeshNode.objects.filter(address__in=addresses, uplink_id=self.uplink_node.address).update(
            uplink_id=None,
        )


class MeshUIConsumer(JsonWebsocketConsumer):
    def connect(self):
        # todo: auth
        self.accept()
        self.msg_sent_filter = {}
        self.msg_received_filter = {}

    def receive_json(self, content, **kwargs):
        if content.get("subscribe", None) == "log":
            async_to_sync(self.channel_layer.group_add)("mesh_log", self.channel_name)
        if content.get("subscribe", None) == "msg_sent":
            async_to_sync(self.channel_layer.group_add)("mesh_msg_sent", self.channel_name)
            self.msg_sent_filter = dict(content.get("filter", {}))
        if content.get("subscribe", None) == "msg_received":
            async_to_sync(self.channel_layer.group_add)("mesh_msg_sent", self.channel_name)
            self.msg_received_filter = dict(content.get("filter", {}))
        if "send_msg" in content:
            msg_to_send = self.scope["session"].pop("mesh_msg_%s" % content["send_msg"], None)
            if not msg_to_send:
                return
            self.scope["session"].save()
            async_to_sync(self.channel_layer.group_add)("mesh_msg_sent", self.channel_name)
            self.msg_sent_filter = {"sender": self.channel_name}
            for recipient in msg_to_send["recipients"]:
                print('send to', recipient)
                MeshMessage.fromjson({
                    'dst': recipient,
                    **msg_to_send["msg_data"],
                }).send(sender=self.channel_name)

    def mesh_log_entry(self, data):
        self.send_json(data)

    def mesh_msg_sent(self, data):
        print('got data', data)
        for key, value in self.msg_sent_filter.items():
            if isinstance(value, list):
                if data.get(key, None) not in value:
                    return
            else:
                if data.get(key, None) != value:
                    return
        self.send_json(data)

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)("mesh_log", self.channel_name)
        async_to_sync(self.channel_layer.group_discard)("mesh_msg_sent", self.channel_name)
        async_to_sync(self.channel_layer.group_discard)("mesh_msg_received", self.channel_name)
