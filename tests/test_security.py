import tempfile
from pathlib import Path

import pytest
from qulab.security import *


def test_password():
    hashed_password = encryptPassword('123')
    assert hashed_password != b'123'
    assert verifyPassword('123', hashed_password) is None
    with pytest.raises(InvalidKey):
        verifyPassword('345', hashed_password)
