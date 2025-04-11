import configparser
import functools
import os
import sys
from pathlib import Path

import click
from loguru import logger

CONFIG_PATH = os.path.expanduser("~/.qulab.ini")
ENV_PREFIX = "QULAB_"


def _get_config_value(option_name,
                      type_cast=str,
                      command_name=None,
                      default=None):
    """支持命令专属配置的优先级获取"""
    # 构造环境变量名
    if command_name:
        env_var = f"{ENV_PREFIX}{command_name.upper()}_{option_name.upper()}"
        config_section = command_name
    else:
        env_var = f"{ENV_PREFIX}{option_name.upper()}"
        config_section = "common"

    # 1. 检查环境变量
    if env_value := os.getenv(env_var):
        if type_cast is bool:
            return env_value.lower() in ("true", "1", "yes")
        if "path" in option_name or issubclass(type_cast, Path):
            return os.path.expanduser(env_value)
        return type_cast(env_value)

    # 2. 检查配置文件
    config = configparser.ConfigParser()
    # 先加载默认配置防止段不存在
    config.read_dict({config_section: {}})
    if Path(CONFIG_PATH).exists():
        config.read(CONFIG_PATH)

    # 从对应配置段读取
    if config.has_section(config_section):
        if config_value := config.get(config_section,
                                      option_name,
                                      fallback=None):
            if type_cast is bool:
                return config_value.lower() in ("true", "1", "yes")
            if "path" in option_name or issubclass(type_cast, Path):
                return os.path.expanduser(config_value)
            return type_cast(config_value)

    return default  # 交给 Click 处理默认值


def get_config_value(option_name,
                     type_cast=str,
                     command_name=None,
                     default=None):
    """
    获取配置值，支持命令专属配置的优先级获取

    优先级：
    1. 命令行参数
    2. 配置文件专属配置
    3. 配置文件公共配置
    4. 环境变量专属配置
    5. 环境变量公共配置
    6. 默认值
    7. Click 处理默认值
    8. None

    Parameters
    ----------
    option_name : str
        配置项名称
    type_cast : type
        转换类型
    command_name : str
        命令名称
        如果为 None，则不使用命令专属配置
    default : any
        默认值
        如果为 None，则不使用默认值
    
    Returns
    -------
    any
        配置值
        如果没有找到配置值，则返回 None
    """
    value = _get_config_value(option_name,
                              type_cast,
                              command_name,
                              default=default)
    if value is None and command_name is not None:
        return _get_config_value(option_name, type_cast, default=default)
    return value


def log_options(func):
    """通用配置装饰器（所有命令共用）"""

    @click.option("--debug",
                  is_flag=True,
                  default=get_config_value("debug", bool),
                  help=f"Enable debug mode")
    @click.option("--log",
                  type=click.Path(),
                  default=lambda: get_config_value("log", Path),
                  help=f"Log file path")
    @click.option("--debug-log",
                  type=click.Path(),
                  default=lambda: get_config_value("debug_log", Path),
                  help=f"Debug log file path")
    @click.option("--quiet",
                  is_flag=True,
                  default=get_config_value("quiet", bool),
                  help=f"Disable log output")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        debug = bool(kwargs.pop("debug"))
        log = kwargs.pop("log")
        debug_log = kwargs.pop("debug_log")
        quiet = bool(kwargs.pop("quiet"))

        if debug:
            log_level = "DEBUG"
        else:
            log_level = "INFO"

        handlers = []
        if log is not None:
            handlers.append(
                dict(sink=log,
                     level="INFO",
                     rotation="monday at 7:00",
                     compression="zip"))
        if debug_log is not None:
            handlers.append(
                dict(sink=debug_log,
                     level="DEBUG",
                     rotation="monday at 7:00",
                     compression="zip"))
        if not quiet or debug:
            handlers.append(dict(sink=sys.stderr, level=log_level))

        logger.configure(handlers=handlers)

        return func(*args, **kwargs)

    return wrapper
