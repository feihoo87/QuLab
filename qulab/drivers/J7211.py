from qulab import BaseDriver, QList, QOption, QReal,QInteger


class Driver(BaseDriver):
    support_models = ['J7211A','J7211B','J7211C',]
    '''Agilent Attenuation Control Unit'''

    quants = [
        QInteger('Att',
              unit='dB',
              set_cmd=':ATT %(value)d',
              get_cmd=':ATT?'),
    ]
