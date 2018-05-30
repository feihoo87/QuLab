# -*- coding: utf-8 -*-
import os
import platform
from pathlib import Path

import yaml

CONFIG_DIRNAME = 'QuLab'
CONFIG_FILENAME = 'config.yaml'
CACHES_DIRNAME = 'caches'
LOG_DIRNAME = 'logs'
DEFAULT_CONFIG = {'db': {'db': 'lab', 'host': 'localhost'}}
CONFIG_TEMPLATE = '''
ca_cert: &ca_cert '{cfg_path}/ca.pem'

db:
  db: lab
  host: [10.122.7.18, 10.122.7.19, 10.122.7.20]
  username: {db_user}
  password: '{db_password}'
  authentication_source: lab
  replicaSet: rs0
  ssl: true
  ssl_ca_certs: *ca_cert
  ssl_match_hostname: true

db_dev:
  db: lab_dev
  host: localhost

server_port: 8123
server_name: ['localhost', '127.0.0.1']
visa_backends: '@py'

ssl:
  ca: *ca_cert
  cert: '{cfg_path}/cert/server.crt'
  key: '{cfg_path}/private/server.key'
'''


def load_config(path):
    return yaml.load(path.read_text())


def config_dir():
    if platform.system() in ['Darwin', 'Linux']:
        home = os.getenv('HOME')
    elif platform.system() == 'Windows':
        home = os.getenv('ProgramData')
    else:
        home = os.getcwd()
    return Path(home) / CONFIG_DIRNAME


def config_file():
    return config_dir() / CONFIG_FILENAME


def caches_dir():
    return config_dir() / CACHES_DIRNAME


def log_dir():
    return config_dir() / LOG_DIRNAME


def create_config(db_user, db_password):
    config_file().parent.mkdir(parents=True, exist_ok=True)
    config_file().write_text(
        CONFIG_TEMPLATE.format(
            db_user=db_user,
            db_password=db_password,
            cfg_path=config_dir().absolute()))


if config_file().exists():
    config = load_config(config_file())
else:
    #create_config()
    config = DEFAULT_CONFIG
