# -*- coding: utf-8 -*-
import datetime
import json
import logging

import tornado.web

from .. import db

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class BaseHandler(tornado.web.RequestHandler):
    '''Base class for HTTP request handlers.
    '''
    sessions = {}

    def initialize(self, instr_mgr, trans):
        self.instr_mgr = instr_mgr
        self.trans = trans

    def get_argument(self, name):
        '''Returns the value of the argument with the given name.
        '''
        if self.request.headers['content-type'].lower() == 'application/x-www-form-urlencoded':
            return super(BaseHandler, self).get_argument(name)
        else:
            data = json.loads(self.request.body.decode('utf-8')).get(name)
            return data

    def get_request_data(self):
        '''
        '''
        if self.request.headers['content-type'].lower() == 'application/x-www-form-urlencoded':
            data = {}
            for k, vlist in self.request.arguments.items():
                data[k] = self.decode_argument(vlist[-1])
        else:
            data = self.trans.decode(json.loads(
                self.request.body.decode('utf-8')))
        return data

    def send_data(self, data):
        self.write(self.trans.encode(data))

    def get_current_user(self):
        user_id = self.get_secure_cookie("user_id", None)
        user_id = None if user_id is None else user_id.decode()
        if user_id in self.sessions.keys():
            return self.sessions[user_id][0]
        else:
            return None

    def login(self, username, password):
        user = db.query.getUserByName(name=username)
        if user is not None and user.hashed_passphrase == password:
            self.set_secure_cookie('user_id', str(user.id))
            self.sessions[str(user.id)] = (user, datetime.datetime.now())
            return True
        else:
            return False

    def logout(self):
        del self.sessions[self.current_user]
        self.clear_all_cookies()

    def options(self):
        pass


class MainHandler(BaseHandler):
    def get(self):
        self.write(
            '<html>'
            '<head>'
            '  <title>Test page</title>'
            '</head>'
            '<body>'
            '  <h1>Test page</h1>'
            '  <div>'
            '    <p>hello, world</p>'
            '  </div>'
            '</body>'
            '</html>'
        )


class LoginHandler(BaseHandler):
    def get(self):
        self.write(
            '<html><body><form action="/login" method="post">'
            'Name: <input type="text" name="user">'
            'Password: <input type="password" name="password">'
            '<input type="submit" value="Sign in">'
            '</form></body></html>'
        )

    def post(self):
        username = self.get_argument('user')
        password = self.get_argument('password')
        succeed = self.login(username, password)
        if succeed:
            self.send_data({'succeed': True})
        else:
            self.send_data({'succeed': False})


class LogoutHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        self.logout()


class OpenInstrumentHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, inst):
        req = self.get_request_data()
        result = {'succeed': False, 'data': 'self'}
        instrument = db.query.getInstrumentByName(name=inst)
        try:
            ins = self.instr_mgr.open_local_resource(instrument, **req['kw'])
            if ins is not None:
                result = {'succeed': True, 'data': 'self'}
        finally:
            self.send_data(result)


class PerformMethodHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, inst, method):
        req = self.get_request_data()
        args = req['args']
        kw = req['kw']
        result = {'succeed': False, 'data': 'self'}
        log.info('instr_mgr[%r].%s(%s, %s)', inst, method, args, kw)
        try:
            ins = self.instr_mgr.get_local_resource(inst)
            res = getattr(ins, method)(*args, **kw)
            result = {'succeed': True, 'data': 'self' if res is ins else res}
        finally:
            self.send_data(result)
