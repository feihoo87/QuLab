# -*- coding: utf-8 -*-
import os
import platform

import yaml

CONFIG_DIRNAME = 'QuLab'
CONFIG_FILENAME = 'config.yaml'
CACHES_DIRNAME = 'caches'
DEFAULT_CONFIG = {
    'db' : {'db': 'lab', 'host': 'localhost'}
}
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

def create_config(db_user, db_password):
    fname = config_file()
    dirname = os.path.dirname(fname)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(fname, 'wt') as f:
        f.write(CONFIG_TEMPLATE.format(
            db_user=db_user,
            db_password=db_password,
            cfg_path=os.path.abspath(config_dir())))

if not os.path.exists(config_file()):
    #create_config()
    config = DEFAULT_CONFIG
else:
    config = load_config(config_file())
