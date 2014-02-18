import ConfigParser
import os


def set_configs():
    config = {}
    confpar = ConfigParser.ConfigParser()
    confpar.readfp(open('/opt/django/configs/apps/ehall.conf'))
    config['APP'] = config.items("APP")

    return config

def get_key(key=''):
