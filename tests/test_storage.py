import time
import unittest

import numpy as np
from qulab.storage import ForgetfulStorage
from qulab.storage.utils import save


class ForgetfulStorageTest(unittest.TestCase):
    def test_storing(self):
        storage = ForgetfulStorage(10)
        storage['one'] = 'two'
        self.assertEqual(storage['one'], 'two')

    def test_forgetting(self):
        storage = ForgetfulStorage(0)
        storage['one'] = 'two'
        self.assertEqual(storage.get('one'), None)

    def test_iter(self):
        storage = ForgetfulStorage(10)
        storage['one'] = 'two'
        for key, value in storage:
            self.assertEqual(key, 'one')
            self.assertEqual(value, 'two')

    def test_iter_old(self):
        storage = ForgetfulStorage(10)
        storage['one'] = 'two'
        for key, value in storage.iter_older_than(0):
            self.assertEqual(key, 'one')
            self.assertEqual(value, 'two')


def test_save(tmpdir):
    p1 = save('test', x=np.array([1, 2, 3]), base_path=tmpdir)
    data = np.load(p1)
    assert data['x'][1] == 2
    time.sleep(1)
    p2 = save('test', x=np.array([1, 2, 3]), base_path=tmpdir)
    assert str(p1) != str(p2)
