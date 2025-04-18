import math
import operator

import numpy as np
import pytest

from qulab.expression import Env, calc


# ----------------------------
# 基础算术运算测试
# ----------------------------
@pytest.mark.parametrize("expression, expected", [
    ("2+3", 5),
    ("10 - 3*2", 4),
    ("3/2", 1.5),
    ("8//3", 2),
    ("7%3", 1),
])
def test_basic_arithmetic(expression, expected):
    result = calc(expression)
    assert result == expected, f"Expected {expected} for {expression}, got {result}"


# ----------------------------
# 运算符优先级测试
# ----------------------------
def test_operator_precedence():
    # 测试普通运算顺序
    assert calc("2+3*4") == 14, "乘法应先于加法执行"
    # 测试括号改变优先级
    assert calc("(2+3)*4") == 20, "括号内应先计算"


# ----------------------------
# 幂运算符测试
# ----------------------------
@pytest.mark.parametrize(
    "expression, expected",
    [
        ("2**3", 8),
        ("2**3**2", 512),  # 解析为 2 ** (3 ** 2) = 512
        ("(2**3)**2", 64)
    ])
def test_power_operator(expression, expected):
    result = calc(expression)
    assert result == expected, f"Expected {expected} for {expression}, got {result}"


# ----------------------------
# 内置数学函数调用测试
# ----------------------------
def test_function_call():
    # sin(pi/2) 约等于1
    result = calc("sin(pi/2)")
    np.testing.assert_almost_equal(result, 1.0, decimal=5)

    # 测试 log, sqrt 等函数
    result_log = calc("log(e)")
    np.testing.assert_almost_equal(result_log, 1.0, decimal=5)

    result_sqrt = calc("sqrt(16)")
    assert result_sqrt == 4, "sqrt(16) 应该等于4"


# ----------------------------
# 变量绑定测试
# ----------------------------
def test_variable_binding():
    # 绑定变量 x=3，计算表达式 x**2 + 1
    result = calc("x**2+1", x=3)
    assert result == 10, "当 x=3 时，x**2+1 应该为10"


# ----------------------------
# 复杂表达式测试
# ----------------------------
def test_complex_expression():
    # 表达式 (x+2)*(x-2) 在 x=5 时应为 21
    result = calc("(x+2)*(x-2)", x=5)
    assert result == 21, "当 x=5 时，(x+2)*(x-2) 应该等于21"


# ----------------------------
# 一元运算符测试
# ----------------------------
@pytest.mark.parametrize("expression, expected", [
    ("-3", -3),
    ("+(3)", 3),
    ("~3", ~3),
])
def test_unary_operator(expression, expected):
    result = calc(expression)
    assert result == expected, f"For expression {expression}, expected {expected}, got {result}"


# ----------------------------
# 位运算符测试
# ----------------------------
@pytest.mark.parametrize("expression, expected", [
    ("5<<1", 10),
    ("8>>2", 2),
])
def test_bit_operator(expression, expected):
    result = calc(expression)
    assert result == expected, f"Bit operation {expression} should result in {expected}"


# ----------------------------
# 浮点数运算和边界条件
# ----------------------------
def test_floating_point():
    # 测试精度：0.1+0.2 可能存在精度问题，故使用近似比较
    result = calc("0.1+0.2")
    np.testing.assert_almost_equal(result, 0.3, decimal=5)


# ----------------------------
# 错误处理测试
# ----------------------------
def test_invalid_expression():
    # 测试解析错误
    with pytest.raises(Exception):
        calc("2+*3")

    # 测试除零错误（可能会抛出 ZeroDivisionError）
    with pytest.raises(ZeroDivisionError):
        calc("10/0")


# ----------------------------
# 多层函数调用和属性访问测试
# ----------------------------
def test_function_and_attribute():
    x = np.array([1.0]) + 2j
    expr = 'x.real'
    result = calc(expr, x=x[0])
    assert result == 1.0, "Expected x.real to be 1.0"

    expr = 'x.tobytes()'
    result = calc(expr, x=x[0])
    assert result == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf0?'

    # 再测试多层函数调用：例如 abs(-sqrt(16))
    result = calc("abs(-sqrt(16))")
    assert result == 4, "Expected abs(-sqrt(16)) == 4"

    result = calc("sin(pi)")
    np.testing.assert_almost_equal(result, 0.0, decimal=5)

    result = calc("cos(pi)")
    np.testing.assert_almost_equal(result, -1.0, decimal=5)

    result = calc("tan(pi/4)")
    np.testing.assert_almost_equal(result, 1.0, decimal=5)


# ----------------------------
# 环境变量测试：修改或添加常量、变量、函数时的行为
# ----------------------------
def test_environment():
    env = Env()
    # 在自定义环境中绑定变量
    env["x"] = 10
    result = calc("x+5", x=env["x"])
    assert result == 15, "通过环境变量传值x=10，应得15"

    # 绑定新变量并验证其值
    env["y"] = 20
    result = calc("x+y", x=env["x"], y=env["y"])
    assert result == 30, "x+y 应为30，当x=10且y=20"
