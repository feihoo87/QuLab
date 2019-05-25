from qulab.driver import BaseDriver
from qulab.loader import loadDriver


def test_loadDriver():
    Driver = loadDriver('TekAWG')
    assert hasattr(Driver, 'create_waveform')
    Driver = loadDriver('PSG')
    assert Driver.support_models == ['E8257D', 'SMF100A', 'SMB100A', 'SGS100A']


def test_load_all():
    dirver_list = [
        '33120A',
        'DPO4104B',
        'NetworkAnalyzer',
        'SR620',
        'AFG3102',
        'DSA875',
        'PSG',
        'TekAWG',
        'HP81110A',
        'RigolAWG',
        'TekAWG70000A',
        'wxAWG',
        'DG645',
        'IT6302',
        'RsFSL',
    ]
    for driver in dirver_list:
        Driver = loadDriver(driver)
        assert issubclass(Driver, BaseDriver)
