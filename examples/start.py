import os
import sys
import time
from pathlib import Path

scripts = [
    'dht.py',
    'instrument.py --name=ATS --model=ATS9870 --driver=AlazarTechDigitizer --address=ATS9870::SYSTEM1::1::INSTR --no-visa',
    'instrument.py --name=AWG --model=AWG5014C --driver=TekAWG --address=TCPIP::192.168.2.106',
    'instrument.py --name=EX --model=E8257D --driver=PSG --address=TCPIP0::192.168.2.102',
    'instrument.py --name=LO --model=D8257D --driver=PSG --address=TCPIP0::192.168.2.121',
    'instrument.py --name=NA --model=N5232A --driver=NetworkAnalyzer --address=TCPIP0::192.168.2.114',
    'jupyter-notebook.py --notebook-dir=D:/notebooks',
]

p = Path(__file__).parent.resolve()

for cmd in scripts:
    os.system('cmd /c start %s %s\\%s' % (sys.executable, p, cmd))
    time.sleep(1)
