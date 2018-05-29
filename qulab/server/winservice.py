import os

import win32event
import win32service
import win32serviceutil
import win32timezone


class PythonService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'QuLabServer'  #服务名称
    _svc_display_name_ = 'QuLab Server'
    _svc_description_ = '提供 QuLab 的仪器控制服务'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.logger = self._getLogger()
        self.server = self._getServer()

    def _getLogger(self):
        import inspect
        import logging
        logger = logging.getLogger('[PythonService]')
        this_file = inspect.getfile(inspect.currentframe())
        dirpath = os.path.abspath(os.path.dirname(this_file))
        handler = logging.FileHandler(os.path.join(dirpath, 'service.log'))
        formatter = logging.Formatter(
            '%(asctime)s  %(name)-12s %(levelname)-8s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def _getServer(self):
        pass

    def SvcDoRun(self):
        self.server.run_for_ever()

    def SvcStop(self):
        self.logger.info('service is stop.')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.server.stop()


if __name__ == '__main__':
    """
    安装服务       python3 winservice.py install
    让服务自动启动  python3 winservice.py --startup auto install
    启动服务       python3 winservice.py start
    重启服务       python3 winservice.py restart
    停止服务       python3 winservice.py stop
    卸载服务       python3 winservice.py remove
    """

    import sys
    import servicemanager
    if len(sys.argv) == 1:
        try:
            evtsrc_dll = os.path.abspath(servicemanager.__file__)
            servicemanager.PrepareToHostSingle(PythonService)
            servicemanager.Initialize('PythonService', evtsrc_dll)
            servicemanager.StartServiceCtrlDispatcher()
        except win32service.error as details:
            import winerror
            if details == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                win32serviceutil.usage()
    else:
        win32serviceutil.HandleCommandLine(PythonService)
