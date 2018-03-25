from notebook.auth.security import passwd, passwd_check

from .base import *


class Role(EmbeddedDocument):
    operate = StringField()
    permission = BooleanField()


class User(Document):
    name = StringField(max_length=50, unique=True)
    email = EmailField(unique=True)
    fullname = StringField(max_length=50)
    hashed_passphrase = StringField(max_length=84)
    roles = EmbeddedDocumentListField(Role)

    @property
    def password(self):
        return self.hashed_passphrase

    @password.setter
    def password(self, passphrase):
        self.hashed_passphrase = passwd(passphrase, algorithm='sha256')

    def check_password(self, passphrase):
        return passwd_check(self.hashed_passphrase, passphrase)

    def __repr__(self):
        return "User(name='%s', email='%s', fullname='%s')" % (self.name,
                                                               self.email,
                                                               self.fullname)

def newUser(**kw):
    return User(**kw)


def getUserByName(name):
    return User.objects(name=name).first()
