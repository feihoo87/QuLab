from qulab.Driver import visaDriver, QInteger, QOption, QReal


class Driver(visaDriver):
    support_models = ['J7211A','J7211B','J7211C',]
    '''Agilent Attenuation Control Unit'''

    quants = [
        QInteger('Att',
              unit='dB',
              set_cmd=':ATT %(value)d',
              get_cmd=':ATT?'),
    ]
