import pytest

from qulab.waveform import *


def test_waveform():
    w = (0.7 * Step(0.7) << 1) - (0.2 * Step(0.2)) - (0.5 * Step(0.5) >> 1)
    assert isinstance(w, Waveform)
