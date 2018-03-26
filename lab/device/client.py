# -*- coding: utf-8 -*-
import requests

from .._bootstrap import get_current_user
from ..db import _schema
from ._driver import DriverManager, parse_resource_name
from .protocol import DEFAULT_PORT, Transport


class CallableAttr:
    def __init__(self, name, parent):
        self.parent = parent
        self.name = name

    def __call__(self, *args, **kwargs):
        return self.parent.performMethod(self.name, args, kwargs)


class InstrumentClient:
    """Client for instrument server."""

    def __init__(self, inst_name, session, timeout=10):
        self.inst_name = inst_name
        self.session = session
        self.transfer = Transport()
        self.timeout = timeout
        self.session.timeout = timeout

    def __repr__(self):
        return 'InstrumentClient(inst_name=%(inst_name)s) on %(server)s' % {
            'inst_name': self.inst_name,
            'server': self.session
        }

    def url(self, api):
        return self.session.get_url(api)

    def set_timeout(self, timeout):
        self.timeout = timeout
        self.session.timeout = timeout
        self.performMethod('set_timeout', (timeout, ), {})
        return self

    def open(self, **kw):
        url = self.url('/api/inst/%s' % self.inst_name)
        kw['timeout'] = self.timeout
        data = {'kw': kw}
        self.session.post(
            url, json=self.transfer.encode(data), timeout=self.timeout)
        return self

    def performMethod(self, method, args, kw):
        url = self.url('/api/inst/%s/%s' % (self.inst_name, method))
        data = {'args': args, 'kw': kw}
        r = self.session.post(
            url, json=self.transfer.encode(data), timeout=self.timeout)
        ret = self.transfer.decode(r.text)
        if ret['succeed'] == False:
            msg = "Error occured when calling inst[%r].%s(%s, %s)" % (
                self.inst_name, method, args, kw)
            raise Exception(msg)
        if isinstance(ret['data'], str) and ret['data'] == 'self':
            return self
        else:
            return ret['data']

    def __getattr__(self, name):
        return CallableAttr(name, self)

    def is_available(self):
        return True


class Session:
    def __init__(self,
                 server,
                 port=DEFAULT_PORT,
                 timeout=10,
                 protocol='https',
                 verify=False):
        self.server = server
        self.port = port
        self.timeout = timeout
        self.protocol = protocol
        self.session = requests.Session()
        self.session.verify = verify

    def __del__(self):
        self.logout()

    def __repr__(self):
        return '%s://%s:%d' % (self.protocol, self.server, self.port)

    def login(self, user, password):
        url = self.get_url('/login')
        resp = self.session.post(
            url,
            json={
                "user": user,
                "password": password
            },
            timeout=self.timeout)

    def logout(self):
        url = self.get_url('/logout')
        resp = self.session.get(url, timeout=self.timeout)

    def get_url(self, api):
        return '%s://%s:%d%s' % (self.protocol, self.server, self.port, api)

    def get(self, *args, **kwargs):
        return self.session.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        resp = self.session.post(*args, **kwargs)
        if resp.status_code == 403:
            user = get_current_user()
            self.login(user.name, user.hashed_passphrase)
            resp = self.session.post(*args, **kwargs)
        elif resp.status_code != 200:
            # raise Error
            pass
        return resp


class InstrumentManager:
    """Manage local instruments and clients of remote instruments."""
    
    def __init__(self, verify, hosts=[], visa_backends='@ni'):
        self.verify = verify
        #self._drvmgr = DriverManager(visa_backends=visa_backends)
        self._drvmgr_py = DriverManager(visa_backends='@py')
        try:
            self._drvmgr_ni = DriverManager(visa_backends='@ni')
        except:
            self._drvmgr_ni = None
        self._sessions = {}
        self._lab = None
        self._hosts = {'localhost'}.union(set(hosts))

    def get_local_resource(self, name):
        ins = self._drvmgr_py.get(name)
        if ins is None:
            ins = self._drvmgr_ni.get(name)
        return ins

    def get_session(self, server, port=DEFAULT_PORT):
        if not ((server, port) in self._sessions.keys()):
            s = Session(server, port, verify=self.verify)
            user = get_current_user()
            s.login(user.name, user.hashed_passphrase)
            self._sessions[(server, port)] = s
        return self._sessions[(server, port)]

    def open_remote_resource(self, instrument, host=None, timeout=10):
        host = instrument.host if host is None else host
        client = InstrumentClient(
            instrument.name, session=self.get_session(host), timeout=timeout)
        client.open()
        return client

    def open_local_resource(self, instrument, timeout=10, **kwds):
        if instrument.host not in self._hosts:
            return None
        protocol, addr = parse_resource_name(instrument.address)
        if protocol in ['TCPIP']:
            return self._drvmgr_py.open(instrument, timeout=timeout, **kwds)
        else:
            return self._drvmgr_ni.open(instrument, timeout=timeout, **kwds)

    def open_resource(self, instrument, host=None, timeout=10):
        if isinstance(instrument, str):
            inst = _schema.getInstrumentByName(instrument)
            if inst is None:
                raise Exception('Instrument %r not found in database.' % instrument)
            else:
                instrument = inst
        if instrument.host == 'localhost' and host is None:
            return self.open_local_resource(instrument, timeout)
        else:
            return self.open_remote_resource(instrument, host, timeout)
