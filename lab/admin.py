import getpass

from . import _bootstrap, db


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


@_bootstrap.require_db_connection
def register():
    username, password, email, fullname = getRegisterInfo()
    user = db.update.newUser(name=username, email=email, fullname=fullname)
    user.password = password
    user.save()
    print('Success.')


@_bootstrap.authenticated
def uploadDriver(path):
    db.update.uploadDriver(path, _bootstrap.get_current_user())


@_bootstrap.authenticated
def setInstrument(name, host, address, driver):
    db.update.setInstrument(name, host, address, driver)
