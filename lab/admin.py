import getpass

from . import _bootstrap
from .db import _schema


def getRegisterInfo():
    username = input('User Name > ')
    password = getpass.getpass(prompt='Password > ')
    password2 = getpass.getpass(prompt='Repeat Password > ')
    if password != password2:
        print('Error')
        return
    email = input('E-mail > ')
    fullname = input('Full Name > ')
    return username, password, email, fullname


def register():
    username, password, email, fullname = getRegisterInfo()
    user = _schema.User(name=username, email=email, fullname=fullname)
    user.password = password
    user.save()
    print('Success.')


@_bootstrap.authenticated
def uploadDriver(path):
    _schema.uploadDriver(path, _bootstrap.get_current_user())
