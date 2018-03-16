# -*- coding: utf-8 -*-
import pickle
import base64
import json

DEFAULT_PORT = 8123

class Transport():
    def __init__(self):
        self.protocol = pickle.HIGHEST_PROTOCOL

    def pack(self, obj):
        buff = pickle.dumps(obj, protocol=self.protocol)
        return base64.b64encode(buff).decode()

    def unpack(self, s):
        buff = base64.b64decode(s)
        return pickle.loads(buff)

    def encode(self, obj, protocol=None):
        protocol = self.protocol if protocol is None else protocol
        data = {
            'protocol': protocol,
            'body': self.pack(obj)
        }
        return json.dumps(data)

    def decode(self, s):
        data = json.loads(s)
        return self.unpack(data['body'])

    def highest_protocol(self):
        return pickle.HIGHEST_PROTOCOL
