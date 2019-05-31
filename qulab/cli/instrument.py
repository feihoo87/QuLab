import asyncio
import pickle

from qulab.loader import loadDriver
from qulab.sugar import getDHT, mount
from qulab.utils import ShutdownBlocker


async def save_config(dht, dev, key):
    while True:
        await dht.set(key, pickle.dumps(dev.config))
        await asyncio.sleep(5)


async def start(args):
    dht = await getDHT()
    Driver = loadDriver(args.driver)
    info = dict(addr=args.address, model=args.model)
    if not args.no_visa:
        import visa
        try:
            rm = visa.ResourceManager()
        except:
            rm = visa.ResourceManager('@py')
        ins = rm.open_resource(args.address)
        info['ins'] = ins
    if args.store_config:
        info['config'] = pickle.loads(await dht.get(args.name + '_config'))
    dev = Driver(**info)
    if args.store_config:
        asyncio.ensure_future(save_config(dht, dev, args.name + '_config'))
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

    parser = argparse.ArgumentParser(description='Run an instrument server.')
    parser.add_argument('--address', '-a', help='instrument address')
    parser.add_argument('--name', '-n', help='instrument name')
    parser.add_argument('--model', '-m', help='instrument model')
    parser.add_argument('--driver', '-d', help='instrument driver')
    parser.add_argument('--no-retry', action='store_true', help='no retry')
    parser.add_argument('--no-visa', action='store_true', help='no visa')
    parser.add_argument('--store-config',
                        action='store_true',
                        help='store config')

    args = parser.parse_args()

    title = f'{args.name} --- {args.model} @ {args.address}'

    if args.no_retry:
        main(args)
    else:
        with ShutdownBlocker(title):
            cmd = [
                sys.executable, __file__, '-a', args.address, '-n', args.name,
                '-m', args.model, '-d', args.driver, '--no-retry'
            ]
            if args.no_visa:
                cmd.append('--no-visa')
            while True:
                proc = subprocess.Popen(cmd)
                proc.wait()
                if proc.returncode == 0:
                    break
