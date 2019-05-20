import secrets

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_SIZE = 16
KEY_SIZE = 32

__all__ = ['InvalidKey', 'encryptPassword', 'verifyPassword']


def encryptPassword(password):
    if isinstance(password, bytes):
        key_material = password
    else:
        key_material = str(password).encode('utf-8')

    salt = secrets.token_bytes(SALT_SIZE)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                     length=KEY_SIZE,
                     salt=salt,
                     iterations=100000,
                     backend=default_backend())
    key = kdf.derive(key_material)
    return salt + key


def verifyPassword(password, hashed_password):
    if isinstance(password, bytes):
        key_material = password
    else:
        key_material = str(password).encode('utf-8')

    salt = hashed_password[:SALT_SIZE]
    key = hashed_password[SALT_SIZE:]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                     length=KEY_SIZE,
                     salt=salt,
                     iterations=100000,
                     backend=default_backend())
    kdf.verify(key_material, key)
