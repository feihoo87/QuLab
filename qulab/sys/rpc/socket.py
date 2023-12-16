from ..net.kcp import listen


class Peer:

    def __init__(self, addr, handler, **kwargs):
        self.addr = addr
        self.handler = handler
        self.kwargs = kwargs

    async def run(self):
        conv = self.kwargs.get('conv', 0)
        ttl = self.kwargs.get('ttl', 60)
        async with listen(self.addr, conv, ttl, **self.kwargs) as server:
            async for conn in server:
                await self.handler(conn)

    def __call__(self, handler):
        self.handler = handler
        return self

    def __await__(self):
        return self.run().__await__()

    def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass
