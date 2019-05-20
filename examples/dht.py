import asyncio
import logging

from qulab.sugar import getDHT
from qulab.utils import ShutdownBlocker


log = logging.getLogger()
log.addHandler(logging.StreamHandler())


async def start():
    dht = await getDHT()
    print('DHT listen on kad://*:%d' % dht.port)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(start(), loop=loop)

    try:
        with ShutdownBlocker('DHT'):
            loop.run_forever()
    except KeyboardInterrupt:
        loop.close()
