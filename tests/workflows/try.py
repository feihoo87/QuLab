def VAR(s):
    pass  # 没有实际作用，只是用来抑制编辑器的警告。


import numpy as np
from loguru import logger

from qulab.typing import Report

# 多长时间应该检查一次校准实验，单位是秒。
__timeout__ = 7 * 24 * 3600


def depends():
    return ['new.py']


def calibrate():
    logger.info(f"running try.py ...")

    # calibrate 是一个完整的校准实验，如power Rabi，Ramsey等。
    # 你需要足够的扫描点，以使得后续的 analyze 可以拟合出合适的参数。

    # 这里只是一个示例，实际上你需要在这里写上你的校准代码。
    x = np.linspace(0, 2 * np.pi, 101)
    y = []
    for i in x:
        y.append(np.sin(i))

    logger.info(f"running try.py ... finished!")
    return x, y


def analyze(report: Report, history: Report | None = None) -> Report:
    """
    分析校准结果。

    report: Report
        本次校准实验的数据。
    history: Report | None
        上次校准实验数据和分析结果，如果有的话。
    """
    import random

    # 这里添加你的分析过程，运行 calibrate 得到的数据，在 report.data 里
    # 你可以得到校准的结果，然后根据这个结果进行分析。
    x, y = report.data

    bad = report.config['bad_qubits']

    # 完整校准后的状态有两种：OK 和 Bad，分别对应校准成功和校准失败。
    # 校准失败是指出现坏数据，无法简单通过重新运行本次校准解决，需要
    # 检查前置步骤。
    report.state = random.choice(['OK', 'Bad'])

    # 参数是一个字典，包含了本次校准得到的参数，后续会更新到config表中。
    report.parameters = {'gate.R.Q1.params.amp': 1}

    # 其他信息可以是任何可序列化的内容，你可以将你想要记录的信息放在这里。
    # 下次校准分析时，这些信息也会在 history 参数中一起传入，帮助你在下
    # 次分析时对比参考。
    report.other_infomation = {}

    return report


def check():
    logger.info(f"checking try.py ...")

    # check 是一个快速检查实验，用于检查校准是否过时。
    # 你只需要少数扫描点，让后续的 check_analyze 知道参数是否漂移，数据
    # 坏没坏就够了，不要求拟合。

    # 这里只是一个示例，实际上你需要在这里写上你的检查代码。
    x = np.linspace(0, 2 * np.pi, 5)
    y = []
    for i in x:
        y.append(np.sin(i))

    logger.info(f"checking try.py ... finished!")
    return x, y


def check_analyze(report: Report, history: Report | None = None) -> Report:
    """
    分析检查结果。

    report: Report
        本次检查实验的数据。
    history: Report | None
        上次检查实验数据和分析结果，如果有的话。
    """
    import random

    # 这里添加你的分析过程，运行 check 得到的数据，在 report.data 里
    # 你可以得到校准的结果，然后根据这个结果进行分析。
    x, y = report.data

    # 状态有三种：Outdated, OK, Bad，分别对应过时、正常、坏数据。
    # Outdated 是指数据过时，即参数漂了，需要重新校准。
    # OK 是指数据正常，参数也没漂，不用重新校准。
    # Bad 是指数据坏了，无法校准，需要检查前置步骤。
    report.state = random.choice(['Outdated', 'OK', 'Bad'])

    return report


def oracle(report: Report,
           history: Report | None = None,
           system_state: dict[str:str] | None = None) -> Report:
    """
    谕示：指凭直觉或经验判断，改动某些配置，以期望下次校准成功。
    
    当校准失败时，根据 analyze 的结果，尝试改变某些配置再重新校准整个系统。
    比如通常我们在死活测不到 rabi 或能谱时，会换一个 idle bias 再试试。这
    里我们凭直觉设的那个 bias 值，就是一个谕示，可以通过 oracle 来设定。

    该函数代入的参数 report 是 analyze 函数的返回值。
    """

    # report.oracle['Q0.bias'] = 0.1
    # report.oracle['Q1.bias'] = -0.03

    return report
