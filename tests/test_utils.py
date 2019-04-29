from qulab.utils import *

def test_utils():
    assert get_unit_prefix(1.23e5) == ('k', 1000.0)