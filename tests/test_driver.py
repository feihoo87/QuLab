import pytest
import visa
from qulab.driver import *


class Driver(BaseDriver):
    error_command = '*ESR?'

    quants = [
        QReal('voltage',
              unit='V',
              set_cmd=':VOLT:IMM:AMPL %(value).3f',
              get_cmd=':VOLT:IMM:AMPL?'),
        QReal('current',
              unit='A',
              set_cmd=':CURR:IMM:AMPL %(value).3f',
              get_cmd=':CURR:IMM:AMPL?'),
        QOption('rail',
                set_cmd='INST %(option)s',
                get_cmd='INST?',
                options=[("A", "P6V"), ("B", "P25V"), ("C", "N25V")]),
        QBool('output', set_cmd='OUTP %(value)d', get_cmd='OUTP?')
    ]


@pytest.fixture
def inst_info():
    rm = visa.ResourceManager('@sim')
    addr = 'ASRL2::INSTR'
    model = 'MOCK'
    ins = rm.open_resource(addr, read_termination='\n')
    yield dict(ins=ins, addr=addr, model=model)
    ins.close()


def test_driver(inst_info):
    dev = Driver(**inst_info)
    dev.setValue('voltage', 2)
    assert dev.getValue('current') == 1
    assert dev.getValue('voltage') == 2
    dev.setValue('rail', 'C')
    assert dev.getValue('rail') == 'N25V'
