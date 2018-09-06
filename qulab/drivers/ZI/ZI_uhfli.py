import logging

import numpy as np
import zhinst.utils

from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector


logger = logging.getLogger('qulab.drivers.ZI')


class Driver(BaseDriver):
    support_models = ['UHFLI', ]
    quants = [

    ]

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.deviceID=kw['deviceID']

    def performOpen(self):
        # self.daq = zhinst.utils.autoConnect()
        apilevel = 6  # The API level supported by this example.
        # Call a zhinst utility function that returns:
        # - an API session `daq` in order to communicate with devices via the data server.
        # - the device ID string that specifies the device branch in the server's node hierarchy.
        # - the device's discovery properties.
        (daq, device, props) = zhinst.utils.create_api_session(self.deviceID, apilevel)
        zhinst.utils.api_server_version_check(daq)
        # Create a base configuration: Disable all available outputs, awgs, demods, scopes,...
        zhinst.utils.disable_everything(daq, device)
        self.daq = daq

    def performSetValue(self, quant, value, **kw):
        pass

    def performGetValue(self, quant, **kw):
        # self.set_configs()
        return quant.getValue(**kw)
