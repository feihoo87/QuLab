from qulab.loader import loadDriver

def test_loadDriver():
    Driver = loadDriver('TekAWG')
    assert hasattr(Driver, 'create_waveform')
    Driver = loadDriver('PSG')
    assert Driver.support_models == ['E8257D', 'SMF100A', 'SMB100A', 'SGS100A']
    