import asyncio
import pathlib
import pickle

import click

from .kad import Server


async def client_get(key, server, port, timeout=5):
    reader, writer = await asyncio.wait_for(asyncio.open_connection(
        server, port),
                                            timeout=timeout)
    writer.write(pickle.dumps(('get', key)))
    await asyncio.wait_for(writer.drain(), timeout=timeout)
    data = await asyncio.wait_for(reader.read(1600), timeout=timeout)
    value = pickle.loads(data)
    writer.close()
    await writer.wait_closed()
    return value


async def client_set(key, value, server, port, timeout=5):
    reader, writer = await asyncio.wait_for(asyncio.open_connection(
        server, port),
                                            timeout=timeout)
    writer.write(pickle.dumps(('set', key, value)))
    await asyncio.wait_for(writer.drain(), timeout=timeout)
    writer.close()
    await writer.wait_closed()


async def client_bootstrap(address, server, port, timeout=5):
    reader, writer = await asyncio.wait_for(asyncio.open_connection(
        server, port),
                                            timeout=timeout)
    addr, p = address.split(':')
    writer.write(pickle.dumps(('bootstrap', (addr, int(p)))))
    await asyncio.wait_for(writer.drain(), timeout=timeout)
    writer.close()
    await writer.wait_closed()


@click.group()
def dht():
    pass


@dht.command()
@click.option('--interface',
              default='127.0.0.1',
              help='Interface to listen on')
@click.option('--port', default=8467, help='Port to listen on')
@click.option('--dht-only', default=False, is_flag=True, help='DHT only')
@click.option('--dht-interface',
              default='0.0.0.0',
              help='DHT interface to listen on')
@click.option('--dht-port', default=8468, help='DHT port to listen on')
@click.option('--bootstrap', default=None, help='Address of bootstrap node')
@click.option('--interval', default=300, help='Refresh interval')
@click.option('--state-file', default=None, help='State file')
def server(interface, port, dht_only, dht_interface, dht_port, bootstrap,
           interval, state_file):

    async def main(interface, port, dht_only, dht_interface, dht_port,
                   bootstrap, state_file):

        if state_file is None:
            state_file = pathlib.Path.home() / '.waveforms' / 'dht.pickle'
        else:
            state_file = pathlib.Path(state_file)

        if state_file.exists():
            node = await Server.load_state(state_file, dht_port, dht_interface,
                                           interval)
        else:
            node = Server()
            state_file.parent.mkdir(parents=True, exist_ok=True)
            await node.listen(dht_port, dht_interface, interval)
        if bootstrap:
            addr, p = bootstrap.split(':')
            await node.bootstrap([(addr, int(p))])

        loop = asyncio.get_running_loop()
        loop.call_later(min(interval / 2, 30), node.save_state_regularly,
                        state_file, interval)

        async def handle_cmds(reader, writer):
            data = await reader.read(1600)
            cmd, *args = pickle.loads(data)
            match cmd:
                case 'get':
                    value = await node.get(*args)
                    data = pickle.dumps(value)
                case 'set':
                    value = await node.set(*args)
                    data = pickle.dumps(value)
                case 'ping':
                    data = pickle.dumps(node.node.id)
                case 'bootstrap':
                    await node.bootstrap(args)
                    data = pickle.dumps(None)
                case _:
                    data = pickle.dumps(None)

            writer.write(data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        if dht_only:
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
        else:
            server = await asyncio.start_server(handle_cmds, interface, port)

            async with server:
                try:
                    await server.serve_forever()
                except asyncio.CancelledError:
                    pass

    asyncio.run(
        main(interface, port, dht_only, dht_interface, dht_port, bootstrap,
             state_file))


@dht.command('get')
@click.argument('key')
@click.option('--server', default='127.0.0.1', help='Server to connect to')
@click.option('--port', default=8467, help='Port to connect to')
@click.option('--timeout', default=5, help='Timeout')
def get(key, server, port, timeout):

    async def client():
        value = await client_get(key, server, port, timeout)
        print(value)

    asyncio.run(client())


@dht.command('set')
@click.argument('key')
@click.argument('value')
@click.option('--server', default='127.0.0.1', help='Server to connect to')
@click.option('--port', default=8467, help='Port to connect to')
@click.option('--timeout', default=5, help='Timeout')
def set_(key, value, server, port, timeout):

    async def client():
        await client_set(key, value, server, port, timeout)

    asyncio.run(client())


@dht.command('bootstrap')
@click.argument('address')
@click.option('--server', default='127.0.0.1', help='Server to connect to')
@click.option('--port', default=8467, help='Port to connect to')
@click.option('--timeout', default=5, help='Timeout')
def bootstrap(address, server, port, timeout):

    async def client():
        await client_bootstrap(address, server, port, timeout)

    asyncio.run(client())
