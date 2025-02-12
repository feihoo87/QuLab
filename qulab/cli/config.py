import configparser
import functools
import os
import sys
from pathlib import Path

import click
from loguru import logger

CONFIG_PATH = os.path.expanduser("~/.qulab.ini")
ENV_PREFIX = "QULAB_"


def _get_config_value(option_name, type_cast=str, command_name=None):
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

    return None  # 交给 Click 处理默认值


def get_config_value(option_name, type_cast=str, command_name=None):
    value = _get_config_value(option_name, type_cast, command_name)
    if value is None and command_name is not None:
        return _get_config_value(option_name, type_cast)
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
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        debug = kwargs.pop("debug")
        log = kwargs.pop("log")
        print(debug, log)
        if log is None and not debug:
            logger.remove()
            logger.add(sys.stderr, level='INFO')
        elif log is None and debug:
            logger.remove()
            logger.add(sys.stderr, level='DEBUG')
        elif log is not None and not debug:
            logger.configure(handlers=[dict(sink=log, level='INFO')])
        elif log is not None and debug:
            logger.configure(handlers=[
                dict(sink=log, level='DEBUG'),
                dict(sink=sys.stderr, level='DEBUG')
            ])
        return func(*args, **kwargs)

    return wrapper
