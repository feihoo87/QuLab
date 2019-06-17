"""
Classfiler

Aquire state of qubits by support vector classification.
"""
import asyncio

from sklearn import svm

from qulab.sugar import getDHT, mount
from qulab.utils import ShutdownBlocker


class Classfiler:
    def __init__(self, N=100):
        self.clfs = [[svm.SVC(kernel='linear'), 0] for i in range(N)]

    def fit(self, index=0, s0, s1):
        s0, s1 = s0[index], s1[index]
        y = [0] * len(s0) + [1] * len(s1)
        x = list(s0) + list(s1)
        self.clfs[index][0].fit(x, y)
        self.clfs[index][1] = self.clfs[index][0].score(x, y)

    def predict(self, data):
        """
        data: Iterable
              data[0], data[1], ... 分别是 Q0, Q1, ... 的数据
        """
        ret = 0
        for i, ((clf, _), s) in enumerate(zip(self.clfs, data)):
            ret += clf.predict(s) << i
        return ret


async def start(args):
    dht = await getDHT()
    dev = Classfiler(args.num)
    await mount(dev, args.name)
    await asyncio.sleep(1)
    print(title, dht.port, await dht.get(args.name))


def main(args):
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(start(args), loop=loop)

    try:
        loop.run_forever()
    finally:
        loop.close()


if __name__ == '__main__':
    import argparse
    import subprocess
    import sys

    parser = argparse.ArgumentParser(description='Run an classfiler server.')
    parser.add_argument('--name',
                        '-n',
                        default='Classfiler',
                        help='server name')
    parser.add_argument('--num',
                        '-N',
                        type=int,
                        default=100,
                        help='number of qubits')
    parser.add_argument('--no-retry', action='store_true', help='no retry')

    args = parser.parse_args()

    title = f'{args.name}'

    if args.no_retry:
        main(args)
    else:
        with ShutdownBlocker(title):
            cmd = [
                sys.executable, __file__, '-n', args.name, '-N', args.num,
                '--no-retry'
            ]
            while True:
                proc = subprocess.Popen(cmd)
                proc.wait()
                if proc.returncode == 0:
                    break
