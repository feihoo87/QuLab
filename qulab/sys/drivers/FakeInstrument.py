from waveforms.sys.device import BaseDevice, exclude, get, set


class Device(BaseDevice):

    channel = [
        'X1', 'X2', 'X3', 'X4', 'Y1', 'Y2', 'Y3', 'Y4', 'Z1', 'Z2', 'Z3', 'Z4',
        'M1', 'M2'
    ]

    @get('IDN')
    def get_idn(self) -> str:
        return 'Fake Instrument'

    @set('{channel}.Vpp', channel=exclude(['M1', 'M2']))
    def set_voltage(self, value: float, channel: str) -> None:
        self.log.info(f'Set {channel} Vpp to {value}')

    @get('{channel}.Vpp', channel=exclude(['M1', 'M2']))
    def get_voltage(self, channel: str, default=0.0) -> float:
        return self._status.get(f'{channel}.Vpp', default)

    @set('{channel}.Offset', channel=exclude(['M1', 'M2']))
    def set_frequency(
        self,
        value: float,
        channel: str,
    ) -> None:
        self.log.info(f'Set {channel} offset to {value}')

    @get('{channel}.Offset', channel=exclude(['M1', 'M2']))
    def get_frequency(self, channel: str, default=0.0) -> float:
        return self._status.get(f'{channel}.Offset', default)

    @set('{channel}.Waveform', channel=exclude(['M1', 'M2']))
    def set_waveform(self, value, channel: str) -> None:
        self.log.info(f'Set {channel} waveform to {value!r}')

    @get('{channel}.Waveform', channel=exclude(['M1', 'M2']))
    def get_waveform(self, channel: str, default=None) -> str:
        return self._status.get(f'{channel}.Waveform', default)

    @set('{channel}.Size', channel=['M1', 'M2'])
    def set_size(self, value, channel: str) -> None:
        self.log.info(f'Set {channel} size to {value!r}')

    @get('{channel}.Trace', channel=['M1', 'M2'])
    def get_size(self, channel: str) -> str:
        import numpy as np
        size = self._status.get(f'{channel}.Size', 1024)
        shots = self._status.get(f'{channel}.Shots', 128)
        return np.random.randn(shots, size)
