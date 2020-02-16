import os
import time

import numpy as np
import logging
log = logging.getLogger(__name__)

# need zhinst package
import zhinst.utils
from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):

    __log__=log
    support_models = [
        'UHFLI',
    ]
    quants = []

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.deviceID = kw['deviceID']

    def performOpen(self):
        # self.daq = zhinst.utils.autoConnect()
        apilevel = 6  # The API level supported by this example.
        # Call a zhinst utility function that returns:
        # - an API session `daq` in order to communicate with devices via the data server.
        # - the device ID string that specifies the device branch in the server's node hierarchy.
        # - the device's discovery properties.
        (daq, device,
         props) = zhinst.utils.create_api_session(self.deviceID, apilevel)
        zhinst.utils.api_server_version_check(daq)
        self.daq = daq
        self.device = device
        self.props = props

    def performSetValue(self, quant, value, **kw):
        pass

    def performGetValue(self, quant, **kw):
        # return quant.getValue(**kw)
        pass

    def load_settings(self, filename):
        if os.path.isabs(filename):
            zhinst.utils.load_settings(self.daq, self.device, filename)
        else:
            path_default = zhinst.utils.get_default_settings_path(self.daq)
            filename = os.path.normpath(os.path.join(path_default, filename))
            zhinst.utils.load_settings(self.daq, self.device, filename)
        time.sleeo(0.5)
        self.daq.sync()

    def save_settings(self, filename):
        if os.path.isabs(filename):
            zhinst.utils.save_settings(self.daq, self.device, filename)
        else:
            path_default = zhinst.utils.get_default_settings_path(self.daq)
            filename = os.path.normpath(os.path.join(path_default, filename))
            dir = os.path.dirname(filename)
            if not os.path.exists(dir):
                os.makedirs(dir)
            zhinst.utils.save_settings(self.daq, self.device, filename)

    def disable_everything(self):
        zhinst.utils.disable_everything(self.daq, self.device)

    def dataaq(self):
        pass
