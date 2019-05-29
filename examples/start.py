import os
import sys
import time

scripts = [
    'qulab.cli.dht',
    'qulab.cli.instrument --name=ATS --model=ATS9870 --driver=AlazarTechDigitizer --address=ATS9870::SYSTEM1::1::INSTR --no-visa',
    'qulab.cli.instrument --name=AWG --model=AWG5014C --driver=TekAWG --address=TCPIP::192.168.1.106',
    'qulab.cli.instrument --name=LO --model=E8257D --driver=PSG --address=TCPIP0::192.168.1.102',
    'qulab.cli.instrument --name=EX --model=D8257D --driver=PSG --address=TCPIP0::192.168.1.121',
    'qulab.cli.instrument --name=NA --model=N5232A --driver=NetworkAnalyzer --address=TCPIP0::192.168.1.114',
    'qulab.cli.notebook --notebook-dir=D:/notebooks',
]

for cmd in scripts:
    os.system('cmd /c start %s -m %s' % (sys.executable, cmd))
    time.sleep(1)
