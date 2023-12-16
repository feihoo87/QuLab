import numpy as np
import pytest

from qulab.scan.base import (BaseOptimizer, Begin, End, OptimizerConfig,
                                 StepStatus, scan_iters)
from qulab.storage.base_dataset import BaseDataset


class FindPeak(BaseOptimizer):

    def __init__(self, dimensions):
        self.index = -1
        self.max_args = dimensions[0]
        self.max_value = -np.inf

    def tell(self, suggested, value):
        args, value = value
        if self.max_value <= value:
            self.max_value = value
            self.max_args = args

    def ask(self):
        self.index += 1
        self.max_value = -np.inf
        return self.max_args,

    def get_result(self):

        class Result():
            x = self.max_args,

        return Result()


def spectrum_func(b, f):
    c = 1 - b**2
    return np.exp(-((f - c) / 0.01)**2)


def spectrum_mask(freq, center=None):
    if center is None:
        return True
    else:
        return -0.1 <= freq - center <= 0.1


@pytest.fixture
def spectrum_data():
    z = np.full((101, 121), np.nan)
    iq = np.full((101, 121, 1024), np.nan, dtype=complex)
    obj = np.full((101, 121), np.nan, dtype=object)
    center = None
    bias_list = np.linspace(-0.1, 0.1, 101)
    freq_list = np.linspace(-0.1, 1.1, 121)

    np.random.seed(1234)
    for i, bias in enumerate(bias_list):
        for j, freq in enumerate(freq_list):
            if spectrum_mask(freq, center):
                z[i, j] = spectrum_func(bias, freq)
                iq[i,
                   j, :] = np.random.randn(1024) + 1j * np.random.randn(1024)
                obj[i, j] = {'a': 1, 'b': 2}
        center = freq_list[np.argmin(np.abs(freq_list - (1 - bias**2)))]
    return {
        'z': z,
        'iq': iq,
        'obj': obj,
        'bias_list': bias_list,
        'freq_list': freq_list
    }


def test_scan_iter():

    def f(a):
        for i in range(5):
            yield a + i, i

    def f2():
        for i in range(2):
            yield i

    def f3():
        for i in range(2):
            yield i * 100, -i * 200

    steps = scan_iters(
        {
            'a': [-1, 1],
            ('b', ('c', 'd')): ([4, 5, 6], f),
            (('e', ), ('g', 'h')): (f2, f3)
        },
        filter=lambda x: x < 8,
        functions={
            'x': lambda a, b: a + b
        })

    def scan_iter2():
        for a in [-1, 1]:
            for b, (c, d) in zip([4, 5, 6], f(a)):
                for e, (g, h) in zip(f2(), f3()):
                    x = a + b
                    if x < 8:
                        yield {
                            'a': a,
                            'b': b,
                            'c': c,
                            'd': d,
                            'e': e,
                            'g': g,
                            'h': h,
                            'x': x
                        }

    for step, args in zip(steps, scan_iter2()):
        for k in ['a', 'b', 'c', 'd', 'e', 'g', 'h', 'x']:
            assert k in step.kwds
            assert step.kwds[k] == args[k]


def test_scan_iter2():

    def gen(a, b, x, y):
        for i in range(a):
            yield b + x + y

    def scan_iter2():
        for a in [1, 2, 3]:
            x = a + 0.5
            for b in x * np.arange(3):
                y = x + a + b
                for c in gen(a, b, x, y):
                    yield {'a': a, 'b': b, 'c': c, 'x': x, 'y': y}

    info = {
        'loops': {
            'a': [1, 2, 3],
            'b': lambda x: x * np.arange(3),
            'c': gen
        },
        'functions': {
            'x': lambda a: a + 0.5,
            'y': lambda a, b, x: x + a + b
        }
    }

    for step, args in zip(scan_iters(**info), scan_iter2()):
        for k in ['a', 'b', 'c', 'x', 'y']:
            assert k in step.kwds
            assert step.kwds[k] == args[k]


def test_scan_iter3():

    N = 3

    def scan_iter2():
        for x0, x1, x2 in zip(*[np.arange(5) + 5 * i for i in range(N)]):
            z0, z1, z2 = x0, x1, x2
            for y0, y1, y2 in zip(*[
                    x0 * np.array([-1, 1]), x1 * np.array([-1, 1]), x2 *
                    np.array([-1, 1])
            ]):
                yield {
                    'x0': x0,
                    'x1': x1,
                    'x2': x2,
                    'y0': y0,
                    'y1': y1,
                    'y2': y2,
                    'z0': z0,
                    'z1': z1,
                    'z2': z2
                }

    info = {
        'loops': {
            tuple([f"x{i}" for i in range(N)]):
            tuple([np.arange(5) + 5 * i for i in range(N)]),
            tuple([f"y{i}" for i in range(N)]):
            tuple([
                lambda i=i, **kw: kw[f"x{i}"] * np.array([-1, 1])
                for i in range(N)
            ]),
        },
        'functions': {
            f"z{i}": lambda i=i, **kw: kw[f"x{i}"]
            for i in range(N)
        }
    }
    for step, args in zip(scan_iters(**info), scan_iter2()):
        for k in ['x0', 'x1', 'x2', 'y0', 'y1', 'y2', 'z0', 'z1', 'z2']:
            assert k in step.kwds
            assert step.kwds[k] == args[k]


def test_scan_iter4():
    return

    def gen(a, b, x, y):
        for i in range(a):
            yield b + x + y

    def scan_iter2():
        for a0, a1 in zip([1, 2, 3], [4, 5, 6]):
            x0 = a0 + 0.5
            x1 = a1 + 0.5
            for b0, b1 in zip(x0 * np.arange(3), x1 * np.arange(3)):
                y0 = x0 + a0 + b0
                y1 = x1 + a1 + b1
                for c0, c1 in zip(gen(a0, b0, x0, y0), gen(a1, b1, x1, y1)):
                    yield {
                        'a0': a0,
                        'b0': b0,
                        'c0': c0,
                        'x0': x0,
                        'y0': y0,
                        'a1': a1,
                        'b1': b1,
                        'c1': c1,
                        'x1': x1,
                        'y1': y1
                    }

    info = {
        'loops': {
            tuple([f'a{i}' for i in range(2)]): ([1, 2, 3], [4, 5, 6]),
            tuple([f'b{i}' for i in range(2)]):
            tuple([
                lambda i=i, **kw: kw[f"x{i}"] * np.arange(3) for i in range(2)
            ]),
            tuple([f'c{i}' for i in range(2)]):
            gen
        },
        'functions': {
            tuple([f'x{i}' for i in range(2)]): lambda a: a + 0.5,
            tuple([f'y{i}' for i in range(2)]): lambda a, b, x: x + a + b
        }
    }

    for step, args in zip(scan_iters(**info), scan_iter2()):
        for k in ['a', 'b', 'c', 'x', 'y']:
            assert k in step.kwds
            assert step.kwds[k] == args[k]


def test_base_dataset(spectrum_data):
    z = spectrum_data['z']
    iq = spectrum_data['iq']
    bias_list = spectrum_data['bias_list']
    freq_list = spectrum_data['freq_list']

    data1 = BaseDataset(save_kwds=False)
    data2 = BaseDataset(save_kwds=True)

    np.random.seed(1234)
    for step in scan_iters(
        {
            ('bias', 'center'):
            (bias_list, OptimizerConfig(FindPeak, [None], max_iters=101)),
            'freq':
            freq_list,
        },
            filter=spectrum_mask,
            trackers=[data1, data2]):
        y = spectrum_func(step.kwds['bias'], step.kwds['freq'])

        step.store({
            'z': y,
            'iq': np.random.randn(1024) + 1j * np.random.randn(1024),
            'obj': {
                'a': 1,
                'b': 2
            }
        })
        step.feedback(('center', ), (step.kwds['freq'], y))

    for data in [data1, data2]:
        assert np.all(bias_list == data['bias'])
        assert np.all(freq_list == data['freq'])
        assert data['z'].shape == (101, 121)
        assert data['iq'].shape == (101, 121, 1024)
        assert np.all((z == data['z'])[np.isnan(z) == False])
        assert np.all((iq == data['iq'])[np.isnan(iq) == False])

    assert set(data1.keys()) == {'bias', 'freq', 'z', 'iq', 'obj'}

    assert set(data2.keys()) == {'bias', 'freq', 'z', 'iq', 'obj', 'center'}
    assert data2['center'].shape == (101, )

    for key in ['z', 'iq', 'obj']:
        assert np.allclose(data1.timestamps[key], data2.timestamps[key])


def test_base_dataset_future(spectrum_data):
    from concurrent.futures import ThreadPoolExecutor

    def init_thread():
        np.random.seed(1234)

    def get_result(bias, freq):
        y = spectrum_func(bias, freq)
        return {
            'z': y,
            'iq': np.random.randn(1024) + 1j * np.random.randn(1024),
            'obj': {
                'a': 1,
                'b': 2
            }
        }

    pool = ThreadPoolExecutor(max_workers=1, initializer=init_thread)

    z = spectrum_data['z']
    iq = spectrum_data['iq']
    bias_list = spectrum_data['bias_list']
    freq_list = spectrum_data['freq_list']

    data = BaseDataset(save_kwds=False)

    for step in scan_iters(
        {
            ('bias', 'center'):
            (bias_list, OptimizerConfig(FindPeak, [None], max_iters=101)),
            'freq':
            freq_list,
        },
            filter=spectrum_mask,
            trackers=[data]):

        fut = pool.submit(get_result, step.kwds['bias'], step.kwds['freq'])

        step.store(fut)
        step.feedback(('center', ), (step.kwds['freq'], fut.result()['z']))

    assert set(data.keys()) == {'bias', 'freq', 'z', 'iq', 'obj'}
    assert np.all(bias_list == data['bias'])
    assert np.all(freq_list == data['freq'])
    assert data['z'].shape == (101, 121)
    assert data['iq'].shape == (101, 121, 1024)
    assert data['obj'].shape == (101, 121)
    assert data['obj'][0, 0] == {'a': 1, 'b': 2}
    assert np.all((z == data['z'])[np.isnan(z) == False])
    assert np.all((iq == data['iq'])[np.isnan(iq) == False])

    pool.shutdown()


def test_level_marker():
    iters = {'a': range(2), 'b': range(2), 'c': range(2)}

    def scan_iter2():
        for a in range(2):
            yield {'a': a}, 0, 'begin'
            for b in range(2):
                yield {'a': a, 'b': b}, 1, 'begin'
                for c in range(2):
                    yield {'a': a, 'b': b, 'c': c}, 2, 'begin'
                    yield {'a': a, 'b': b, 'c': c}, 2, 'step'
                    yield {'a': a, 'b': b, 'c': c}, 2, 'end'
                yield {'a': a, 'b': b}, 1, 'end'
            yield {'a': a}, 0, 'end'

    for step, args in zip(scan_iters(iters, level_marker=True), scan_iter2()):
        kw, level, marker = args
        assert step.kwds == kw
        if marker == 'begin':
            assert isinstance(step, Begin)
            assert step.level == level
        elif marker == 'step':
            assert isinstance(step, StepStatus)
        elif marker == 'end':
            assert isinstance(step, End)
            assert step.level == level
