# -*- coding: utf-8 -*-
import os
import platform

import yaml

CONFIG_DIRNAME = 'QuLab'
CONFIG_FILENAME = 'config.yaml'
CACHES_DIRNAME = 'caches'

CA_CERT = '''-----BEGIN CERTIFICATE-----
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
-----END CERTIFICATE-----
'''
DEFAULT_CONFIG = '''
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

def load_config(fname):
    with open(fname, 'r') as f:
        config = yaml.load(f.read())
    return config

def config_dir():
    if platform.system() in ['Darwin', 'Linux']:
        home = os.getenv('HOME')
    elif platform.system() == 'Windows':
        home = os.getenv('ProgramData')
    else:
        home = os.getcwd()
    return os.path.join(home, CONFIG_DIRNAME)

def config_file():
    return os.path.join(config_dir(), CONFIG_FILENAME)

def caches_dir():
    return os.path.join(config_dir(), CACHES_DIRNAME)

def create_config():
    fname = config_file()
    dirname = os.path.dirname(fname)
    ca_path = os.path.join(dirname, 'ca.pem')
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    if not os.path.exists(ca_path):
        with open(ca_path, 'wt') as f:
            f.write(CA_CERT)
    with open(fname, 'wt') as f:
        f.write(DEFAULT_CONFIG.format(cfg_path=os.path.abspath(config_dir())))

if not os.path.exists(config_file()):
    create_config()

config = load_config(config_file())
