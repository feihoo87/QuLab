import pickle
import threading
import time

import pyperclip
import zmq

from .storage import Report

# 需要复制到 Notebook 的代码模板
clip_template = """
from qulab.executor.analyze import get_report as get_report_{server_port}

report, history = get_report_{server_port}("tcp://{server_address}:{server_port}")
# 在这里插入数据处理逻辑

{analysis_code}
"""

analysis_code = """
# report.state = 'OK'
# report.parameters = {}
# report.oracle = {}
# report.other_infomation = {}

report.parameters

"""


# ZeroMQ 服务线程，用于响应 Notebook 的请求
class ServerThread(threading.Thread):

    def __init__(self, data, timeout):
        super().__init__()
        self.data = data
        self.result = None
        self.port = 0
        self.timeout = timeout
        self.running = True
        self.finished = threading.Event()
        self.context = zmq.Context()

    def find_free_port(self):
        with zmq.Socket(self.context, zmq.REQ) as s:
            s.bind_to_random_port("tcp://*")
            self.port = int(
                s.getsockopt(zmq.LAST_ENDPOINT).decode().split(":")[-1])
            s.unbind(s.getsockopt(zmq.LAST_ENDPOINT))
        return self.port

    def run(self):
        self.port = self.find_free_port()
        socket = self.context.socket(zmq.REP)
        socket.bind(f"tcp://*:{self.port}")
        # 设置 recv 超时 1 秒
        socket.RCVTIMEO = 1000
        start_time = time.time()
        try:
            while self.running and (time.time() - start_time < self.timeout):
                try:
                    msg = socket.recv()
                except zmq.Again:
                    continue  # 超时后继续等待

                # Notebook 端请求数据
                if msg == b"GET":
                    socket.send(pickle.dumps(self.data))
                else:
                    # Notebook 端提交了处理结果
                    try:
                        self.result = pickle.loads(msg)
                    except Exception as e:
                        # 如果解析失败，也返回默认 ACK
                        self.result = None
                    socket.send(b"ACK")
                    self.running = False
                    break
        finally:
            socket.close()
            self.context.term()
            self.finished.set()

    def stop(self):
        self.running = False
        self.finished.set()

    def wait_for_result(self):
        self.finished.wait()
        return self.result


# 进入分析流程，启动服务并打印等待提示
def get_result_or_wait_until_timeout(report: Report, history: Report | None,
                                     timeout: float) -> Report:
    server = ServerThread((report, history), timeout)
    server.start()

    parameters = report.parameters
    oracle = report.oracle
    other_infomation = report.other_infomation
    state = report.state

    # 格式化代码模板
    code = clip_template.format(server_address="127.0.0.1",
                                server_port=server.port,
                                analysis_code=analysis_code)

    # 将代码复制到剪切板
    pyperclip.copy(code)

    # 同时打印到终端，防止误操作导致剪切板内容丢失
    print("请在 Jupyter Notebook 中运行下面这段代码：")
    print("-" * 60)
    print(code)
    print("-" * 60)
    print("等待 Notebook 提交处理结果，或等待超时（{} 秒）...".format(timeout))

    start_time = time.time()
    # 采用循环等待提交结果，间隔 0.5 秒检测一次
    while server.finished.wait(timeout=0.5) is False:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            # 超时后结束等待
            server.stop()
            break

    result = server.wait_for_result()
    if result is None:
        return (state, parameters, oracle, other_infomation, code)
    else:
        return result


def manual_analysis(report: Report, history=None, timeout=3600):
    try:
        (state, parameters, oracle, other_infomation,
         code) = get_result_or_wait_until_timeout(report, history, timeout)
        report.parameters = parameters
        report.oracle = oracle
        report.state = state
        report.other_infomation = other_infomation
    except Exception as e:
        pass
    return report


def get_report(address: str) -> Report:
    import IPython

    ipy = IPython.get_ipython()
    if ipy is None:
        raise RuntimeError("请在 Jupyter Notebook 中运行此函数。")
    ipy.set_next_input(("from qulab.executor.analyze import submit_report\n"
                        "# 处理完成后，提交结果\n"
                        f"# submit_report(report, \"{address}\")"),
                       replace=False)
    context = zmq.Context()
    sock = context.socket(zmq.REQ)
    sock.connect(address)
    # 请求数据
    sock.send(b"GET")
    report, history = pickle.loads(sock.recv())
    return report, history


def submit_report(report: Report, address: str):
    import IPython

    ipy = IPython.get_ipython()
    if ipy is None:
        raise RuntimeError("请在 Jupyter Notebook 中运行此函数。")

    code = ipy.user_ns['In'][-2]

    parameters = report.parameters
    oracle = report.oracle
    other_infomation = report.other_infomation
    state = report.state

    context = zmq.Context()
    sock = context.socket(zmq.REQ)
    sock.connect(address)
    # 提交处理后的结果
    sock.send(pickle.dumps(
        (state, parameters, oracle, other_infomation, code)))
    ack = sock.recv()
    print("结果已提交。")
