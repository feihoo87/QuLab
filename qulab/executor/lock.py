import json
import socket
import time
import uuid
from contextlib import contextmanager
from multiprocessing import Manager, Process

UDP_PORT = 55555
BROADCAST_ADDR = '<broadcast>'
RESPONSE_TIMEOUT = 1  # 单次等待响应时间
ATTEMPTS = 3  # 获取锁尝试次数


class UDPLock:

    def __init__(self):
        self.uuid = str(uuid.uuid4())
        self.manager = Manager()
        self.queue = self.manager.list()  # 全局任务队列
        self.addr_map = self.manager.dict()  # UUID到地址的映射
        self.listener = None
        self.listening_port = None
        self.has_lock = False

    def __enter__(self):
        # 启动监听进程并获取监听端口
        port_queue = self.manager.Queue()
        self.listener = Process(target=self._start_listener,
                                args=(port_queue, ))
        self.listener.start()
        self.listening_port = port_queue.get(timeout=5)

        # 尝试获取锁
        self._acquire_lock()
        return self

    def __exit__(self, *args):
        # 释放锁并清理资源
        if self.has_lock:
            with self.queue.get_lock():
                if self.queue and self.queue[0] == self.uuid:
                    self.queue.pop(0)
        if self.listener:
            self.listener.terminate()
            self.listener.join()

    def _start_listener(self, port_queue):
        """监听进程主函数"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', 0))
        self.listening_port = sock.getsockname()[1]
        port_queue.put(self.listening_port)

        while True:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                self._handle_message(msg, addr, sock)
            except Exception as e:
                pass

    def _handle_message(self, msg, addr, sock):
        """处理接收到的消息"""
        if msg['type'] == 'DISCOVER':
            # 记录新节点信息并回复当前队列
            self.addr_map[msg['uuid']] = (addr[0], msg['port'])
            response = {
                'type': 'RESPONSE',
                'queue': list(self.queue),
                'addr_map': dict(self.addr_map)
            }
            sock.sendto(json.dumps(response).encode(), (addr[0], msg['port']))

        elif msg['type'] == 'RESPONSE':
            # 合并队列信息
            with self.queue.get_lock():
                existing = set(self.queue)
                self.queue.extend(
                    [u for u in msg['queue'] if u not in existing])
                self.addr_map.update(msg['addr_map'])

        elif msg['type'] == 'PING':
            # 响应存活检查
            if msg['target'] == self.uuid:
                sock.sendto(json.dumps({'type': 'PONG'}).encode(), addr)

    def _acquire_lock(self):
        """尝试获取锁的核心逻辑"""
        for _ in range(ATTEMPTS):
            # 发送发现广播
            self._send_discovery()
            start = time.time()

            # 等待响应
            while time.time() - start < RESPONSE_TIMEOUT:
                time.sleep(0.1)
                if self.queue and self.queue[0] == self.uuid:
                    self.has_lock = True
                    return

        # 三次尝试后仍无响应则加入队列
        with self.queue.get_lock():
            if self.uuid not in self.queue:
                self.queue.append(self.uuid)

        # 等待直到成为队首
        while not self.has_lock:
            self._check_queue_status()
            time.sleep(RESPONSE_TIMEOUT)

    def _send_discovery(self):
        """发送节点发现广播"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = {
            'type': 'DISCOVER',
            'uuid': self.uuid,
            'port': self.listening_port
        }
        sock.sendto(json.dumps(msg).encode(), (BROADCAST_ADDR, UDP_PORT))
        sock.close()

    def _check_queue_status(self):
        """检查队列状态并更新锁"""
        with self.queue.get_lock():
            if not self.queue:
                self.has_lock = True
                return

            # 移除非存活节点
            alive_nodes = []
            for u in self.queue:
                if self._is_alive(u):
                    alive_nodes.append(u)
                else:
                    del self.addr_map[u]
            self.queue[:] = alive_nodes

            # 检查是否轮到自己
            if self.queue and self.queue[0] == self.uuid:
                self.has_lock = True

    def _is_alive(self, target_uuid):
        """检查指定UUID是否存活"""
        if target_uuid not in self.addr_map:
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(RESPONSE_TIMEOUT)
            addr = self.addr_map[target_uuid]
            sock.sendto(
                json.dumps({
                    'type': 'PING',
                    'target': target_uuid
                }).encode(), addr)
            sock.recvfrom(1024)
            return True
        except:
            return False
        finally:
            sock.close()


@contextmanager
def cross_process_lock():
    lock = UDPLock()
    try:
        with lock:
            yield
    finally:
        pass


# 使用示例
if __name__ == '__main__':
    with cross_process_lock():
        print(f'Running critical section with UUID: {uuid.uuid4()}')
        time.sleep(10)  # 模拟耗时操作
