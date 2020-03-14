import functools
import profile
from bisect import bisect_left
from itertools import product

import numpy as np
import scipy.special as special

_zero = ((), ())


def _const(c):
    return (((), ()), ), (c, )


_one = _const(1)
_half = _const(1/2)


def _is_const(x):
    return len(x[0]) == 1 and x[0][0][0] == ()


def _basic_wave(Type, *args, shift=0):
    return ((((Type, shift, *args), ), (1, )), ), (1, )


def _insert_type_value_pair(t_list, v_list, t, v, lo, hi):
    i = bisect_left(t_list, t, lo, hi)
    if i < hi and t_list[i] == t:
        v += v_list[i]
        if v == 0:
            t_list.pop(i)
            v_list.pop(i)
            return i, hi - 1
        else:
            v_list[i] = v
            return i, hi
    else:
        t_list.insert(i, t)
        v_list.insert(i, v)
        return i, hi + 1


def _mul(x, y):
    t_list, v_list = [], []
    xt_list, xv_list = x
    yt_list, yv_list = y
    lo, hi = 0, 0
    for (t1, t2), (v1, v2) in zip(
            product(xt_list, yt_list), product(xv_list, yv_list)):
        if v1 * v2 == 0:
            continue
        t = _add(t1, t2)
        lo, hi = _insert_type_value_pair(t_list, v_list, t, v1 * v2, lo, hi)
    return tuple(t_list), tuple(v_list)


def _add(x, y):
    if x == _zero:
        return y
    if y == _zero:
        return x
    x, y = (x, y) if len(x[0]) >= len(y[0]) else (y, x)
    t_list, v_list = list(x[0]), list(x[1])
    lo, hi = 0, len(t_list)
    for t, v in zip(*y):
        lo, hi = _insert_type_value_pair(t_list, v_list, t, v, lo, hi)
    return tuple(t_list), tuple(v_list)


def _shift(x, time):
    if x == _zero or _is_const(x):
        return x

    t_list = []

    for pre_mtlist, nlist in x[0]:
        mtlist = []
        for mt in pre_mtlist:
            mtlist.append((mt[0], mt[1] + time, *mt[2:]))
        t_list.append((tuple(mtlist), nlist))
    return tuple(t_list), x[1]


def _pow(x, n):
    if x == _zero:
        return _zero
    if n == 0:
        return _one
    if _is_const(x):
        return _const(x[1][0]**n)

    t_list, v_list = [], []

    for (mtlist, pre_nlist), v in zip(*x):
        nlist = []
        for m in pre_nlist:
            nlist.append(n * m)
        t_list.append((mtlist, tuple(nlist)))
        v_list.append(v**n)
    return tuple(t_list), tuple(v_list)


# def _reciprocal(x):
#     if x == _zero:
#         raise ZeroDivisionError('division by waveform contained zero')
#     if _is_const(x):
#         return _const(1/x[1][0])
#     t_list, v_list = [], []

#     for (mtlist, pre_nlist), v in zip(*x):
#         nlist = []
#         for n in n_mtlist:
#             ntlist.append(-n)
#         t_list.append((mtlist, tuple(nlist)))
#         v_list.append(1/v)
#     return tuple(t_list), tuple(v_list)


#@functools.lru_cache(maxsize=128)
def _apply(x, Type, shift, *args):
    return _baseFunc[Type](x - shift, *args)


def _calc(wav, x):
    lru_cache = {}

    def _calc_m(t, x):
        ret = 1
        for mt, n in zip(*t):
            lru_cache[mt] = lru_cache.get(mt, _apply(x, *mt))
            ret = ret * lru_cache[mt]**n
        return ret

    ret = 0
    for t, v in zip(*wav):
        ret = ret + v * _calc_m(t, x)
    return ret


class Waveform:
    __slots__ = ('bounds', 'seq')

    def __init__(self, bounds=(+np.inf, ), seq=(_zero, )):
        self.bounds = bounds
        self.seq = seq

    def _comb(self, other, oper):
        bounds = []
        seq = []
        i1, i2 = 0, 0
        h1, h2 = len(self.bounds), len(other.bounds)
        while i1 < h1 or i2 < h2:
            seq.append(oper(self.seq[i1], other.seq[i2]))
            b = min(self.bounds[i1], other.bounds[i2])
            bounds.append(b)
            if b == self.bounds[i1]:
                i1 += 1
            if b == other.bounds[i2]:
                i2 += 1
        return Waveform(tuple(bounds), tuple(seq))

    def __pow__(self, n):
        return Waveform(self.bounds, tuple(_pow(w, n) for w in self.seq))

    def __add__(self, other):
        if isinstance(other, Waveform):
            return self._comb(other, _add)
        else:
            return self + const(other)

    def __radd__(self, v):
        return const(v) + self

    def append(self, other):
        if not isinstance(other, Waveform):
            raise TypeError('connect Waveform by other type')
        if len(self.bounds) == 1:
            self.bounds = other.bounds
            self.seq = self.seq + other.seq[1:]
            return

        assert self.bounds[-2] <= other.bounds[
            0], f"connect waveforms with overlaped domain {self.bounds}, {other.bounds}"
        if self.bounds[-2] < other.bounds[0]:
            self.bounds = self.bounds[:-1] + other.bounds
            self.seq = self.seq + other.seq[1:]
        else:
            self.bounds = self.bounds[:-2] + other.bounds
            self.seq = self.seq[:-1] + other.seq[1:]

    def __ior__(self, other):
        self.append(other)
        return self

    def __or__(self, other):
        w = Waveform(self.bounds, self.seq)
        w.append(other)
        return w

    def __mul__(self, other):
        if isinstance(other, Waveform):
            return self._comb(other, _mul)
        else:
            return self * const(other)

    def __rmul__(self, v):
        return const(v) * self

    def __truediv__(self, other):
        if isinstance(other, Waveform):
            raise TypeError('division by waveform')
        else:
            return self * const(1 / other)

    def __neg__(self):
        return -1 * self

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, v):
        return v + (-self)

    def __rshift__(self, time):
        return Waveform(
            tuple(bound + time for bound in self.bounds),
            tuple(_shift(expr, time) for expr in self.seq))

    def __lshift__(self, time):
        return self >> (-time)

    def __call__(self, x):
        range_list = np.searchsorted(x, self.bounds)
        ret = np.zeros(x.shape)
        start, stop = 0, 0
        for i, stop in enumerate(range_list):
            if start < stop and self.seq[i] != _zero:
                ret[start:stop] = _calc(self.seq[i], x[start:stop])
            start = stop
        return ret

    def __hash__(self):
        return hash((self.bounds, self.seq))


_zero_waveform = Waveform()
_one_waveform = Waveform(seq=(_one, ))

def zero():
    return _zero_waveform

def one():
    return _one_waveform

def const(c):
    return Waveform(seq=(_const(c), ))


LINEAR = 1
GAUSSIAN = 2
ERF = 3
COS = 4
SIN = 5

_baseFunc = {
    LINEAR: lambda t: t,
    GAUSSIAN: lambda t, std_sq2: np.exp(-(t / std_sq2)**2),
    ERF: lambda t, std_sq2: special.erf(t / std_sq2),
    COS: lambda t, w: np.cos(w * t),
    SIN: lambda t, w: np.sin(w * t)
}


def _D_base(m):
    Type, shift, *args = m
    return {
        LINEAR: _one_waveform,
        GAUSSIAN: (((((GAUSSIAN, shift, *args), (LINEAR, shift)), (1, 1)), ), (-2/args[0]**2, )),
        ERF: (((((GAUSSIAN, shift, *args), ), (1, )), ), (2/args[0]/np.sqrt(np.pi), )),
        COS: (((((SIN, shift, *args), ), (1, )), ), (-args[0], )),
        SIN: (((((COS, shift, *args), ), (1, )), ), (args[0], )),
    }[Type]


def _D(x):
    if x == _zero or _is_const(x):
        return _zero
    t_list, v_list = x
    if len(t_list) == 1:
        (m_list, n_list), v = t_list[0], v_list[0]
        if len(m_list) == 1:
            m, n = m_list[0], n_list[0]
            if n == 1:
                return _mul(_D_base(m), _const(v))
            else:
                return _mul((((m, ), (n-1,)) , (n*v,)) , _D((((m, ), (1,)) , (1,))))
        else:
            a, b = ((m_list[:1],n_list[:1]), (v,)), ((m_list[1:],n_list[1:]), (1,)*(len(m_list)-1))
            return _add(_mul(a, _D(b)), _mul(_D(a), b))
    else:
        return _add(_D((t_list[:1], v_list[:1])), _D((t_list[1:], v_list[1:])))


def D(wav):
    """derivative
    """
    return Waveform(
        bounds = wav.bounds,
        seq = tuple(_D(x) for x in wav.seq)
    )


def step(edge):
    std_sq2 = edge / 5
    return Waveform(
        bounds=(-edge, edge, +np.inf),
        seq=(_zero, _add(_half, _mul(_half, _basic_wave(ERF, std_sq2))), _one))


def square(width):
    return Waveform(
        bounds=(-0.5 * width, 0.5 * width, +np.inf),
        seq=(_zero, _one, _zero))


def gaussian(width):
    # width is two times FWHM
    std_sq2 = width / (4 * np.sqrt(np.log(2)))
    # std is set to give total pulse area same as a square
    #std_sq2 = width/np.sqrt(np.pi)
    return Waveform(
        bounds=(-0.5 * width, 0.5 * width, +np.inf),
        seq=(_zero, _basic_wave(GAUSSIAN, std_sq2), _zero))


def cos(w, phi=0):
    return Waveform(seq=(_basic_wave(COS, w, shift=-phi / w), ))


def sin(w, phi=0):
    return Waveform(seq=(_basic_wave(SIN, w, shift=-phi / w), ))


def cosPulse(width):
    cos = _basic_wave(COS, 2*np.pi/width)
    pulse = _mul(_add(cos, _one), _half)
    return Waveform(
        bounds=(-0.5 * width, 0.5 * width, +np.inf),
        seq=(_zero, pulse, _zero))


def _poly(*a):
    """
    a[0] + a[1] * t + a[2] * t**2 + ...
    """
    return (((), ()), ) + tuple([((LINEAR, 0), (n,)) for n, _ in enumerate(a[:1], start=1)]) , a


def poly(a):
    """
    a[0] + a[1] * t + a[2] * t**2 + ...
    """
    return Waveform(seq=(_poly(*a), ))


def mixing(pulse, phase=0.0, freq=None, ratioIQ=1.0, phaseDiff=0.0, DRAGScaling=None):
    """SSB or envelope mixing
    """
    if DRAGScaling is not None:
        # apply DRAG
        I = pulse
        Q = DRAGScaling * D(pulse)
    else:
        I = pulse
        Q = zero()

    if freq is not None:
        # SSB mixing
        Iout = I * cos(2*np.pi*freq, -phase) - Q * cos(2*np.pi*freq, -phase+np.pi/2)
        Qout = -I * sin(2*np.pi*freq, -phase + phaseDiff) + Q * sin(2*np.pi*freq, -phase+np.pi/2 + phaseDiff)
        Qout = ratioIQ * Qout
    else:
        # envelope mixing
        Iout = I * np.cos(-phase) - Q * np.cos(-phase+np.pi/2)
        Qout = -I * np.sin(-phase) + Q * np.sin(-phase+np.pi/2)
    return Iout, Qout


__all__ = ['Waveform', 'D', 'zero', 'const', 'step', 'square', 'gaussian', 'cos', 'sin', 'cosPulse', 'poly', 'mixing']
