from ConfigParser import ConfigParser
import re
import os
import logging

log = logging.getLogger(__name__)

config = ConfigParser()
config.read(os.environ.get('FUNNEL_CONFIG') or '/etc/funnel/config.cfg')

def config_reader(section):
    class F:
        @classmethod
        def get(cls, x):
            global config
            return config.get(section, x)
    return F



