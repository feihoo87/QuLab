import os
import sys
import time

scripts = [
    'dht.py',
    'instrument.py --name=ATS --model=ATS9870 --driver=AlazarTechDigitizer --address=ATS9870::SYSTEM1::1::INSTR --no-visa',
    'instrument.py --name=AWG --model=AWG5014C --driver=TekAWG --address=TCPIP::192.168.2.106',
    'instrument.py --name=EX --model=E8257D --driver=PSG --address=TCPIP0::192.168.2.102',
    'instrument.py --name=LO --model=D8257D --driver=PSG --address=TCPIP0::192.168.2.121',
    'instrument.py --name=LO --model=N5232A --driver=NetworkAnalyzar --address=TCPIP0::192.168.2.121',
    'jupyter-notebook.py --notebook-dir=C:/WPy64-3720/notebooks',
]

for cmd in scripts:
    os.system('cmd /c start %s %s' % (sys.executable, cmd))
    time.sleep(1)
