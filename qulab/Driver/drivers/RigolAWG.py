import numpy as np

from qulab.Driver import visaDriver, QReal


class Driver(visaDriver):
    support_models = ['DG1062Z']
    CHs=[1,2]

    quants = [

        # Set the waveform of the specified channel to DC with the specified offset.
        QReal('Offset',
              value=0,
              unit='VDC',
              ch=1,
              set_cmd=':SOUR%(ch)d:APPL:DC 1,1, %(value).8e%(unit)s',
              get_cmd=''),

    ]
