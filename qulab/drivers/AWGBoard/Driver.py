from qulab import BaseDriver
from . import AWGboard


class Driver(BaseDriver):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.board = AWGboard.AWGboard()
        self.board.connect(kw.get('addr'))
        self.board.InitBoard()
        self._output_status = [0, 0, 0, 0]

    def __del__(self):
        self.board.disconnect()

    def on(self, ch=1):
        self.board.Start(ch)
        self._output_status[ch - 1] = 1

    def off(self, ch=1):
        self.board.Stop(ch)
        self._output_status[ch - 1] = 0

    def setWaveform(self,
                    points,
                    ch=1,
                    wtype='trig',
                    delay=0,
                    is_continue=False):
        wlist = [self.board.gen_wave_unit(points, wtype, delay)]
        self.board.wave_compile(ch, wlist, is_continue=is_continue)
        for index, on in enumerate(self._output_status):
            if on:
                self.Start(index + 1)

    def setVpp(self, vpp, ch=1):
        vpp = min(abs(vpp), 1.351)
        volt = 1.351
        gain = vpp / volt
        self.board.set_channel_gain(ch, gain)
        self.board._SetDACMaxVolt(ch, volt)

    def setOffset(self, offs, ch=1):
        self.board.SetOffsetVolt(ch, offs)
