import numpy as np
from config import config
from waveforms.dicttree import _eq

from qulab.registry import DELETE, Registry, TreeRef


def test_registry():
    reg = Registry.from_url('sqlite:///:memory:')
    assert reg.export() == {}

    reg.set('test.a.b', 12.5)
    assert reg.export() == {'test': {'a': {'b': 12.5}}}

    reg.update({'test': {'x': 'hello'}})
    assert reg.export() == {'test': {'x': 'hello', 'a': {'b': 12.5}}}

    reg.update(
        {'dev': {
            'a': '12',
            'b': 'tcp',
            'c': 11283,
            'd': np.arange(10)
        }})

    assert np.equal(reg.get('dev.d[::2]'), np.array([0, 2, 4, 6, 8])).all()
    assert _eq(
        reg.export(), {
            'test': {
                'x': 'hello',
                'a': {
                    'b': 12.5
                }
            },
            'dev': {
                'a': '12',
                'b': 'tcp',
                'c': 11283,
                'd': np.arange(10)
            }
        })

    reg.update({'dev': {'b': {'c': 12}, 'c': DELETE}})
    assert _eq(
        reg.export(), {
            'test': {
                'x': 'hello',
                'a': {
                    'b': 12.5
                }
            },
            'dev': {
                'a': '12',
                'd': np.arange(10),
                'b': {
                    'c': 12
                }
            }
        })

    assert reg.get('dev.c') is None
    assert reg.previous().get('dev.c') == 11283
    assert _eq(reg.get('dev.d'), np.arange(10))
    assert _eq(reg.previous().get('dev.d'), np.arange(10))


def test_search():
    reg = Registry.from_url('sqlite:///:memory:')
    reg.update(config)

    ret = reg.export(depth=1)

    assert set(ret.keys()) == {'__version__', 'station', 'chip', 'gates'}
    assert all(
        isinstance(ret[k], TreeRef) for k in ['station', 'chip', 'gates'])
    assert ret['__version__'] == 1

    assert reg.get('gates.rfUnitary.Q1.params.amp[1][1]') == 0.8204
    assert list(reg.search('gates.rfUnitary.*.params.amp[1][1]')) == [
        ('gates.rfUnitary.Q1.params.amp[1][1]', 0.8204),
        ('gates.rfUnitary.Q2.params.amp[1][1]', 0.658)
    ]

    for k, v in reg.search('gates.!rfUnitary.*.params'):
        assert k.startswith('gates.') and k.endswith('.params')
        assert not k.startswith('gates.rfUnitary')
        assert isinstance(v, TreeRef)

    for k, v in reg.search('gates.*.*.*.dur*'):
        assert k.endswith('.duration')
        assert isinstance(v, (list, float))

    for k, v in reg.search('gates.*.*.*.dur*[1][1]'):
        assert k.startswith('gates.rfUnitary.Q') and k.endswith(
            '.params.duration[1][1]')
        assert isinstance(v, float)
