from ConfigParser import ConfigParser
import re

config = ConfigParser()
config.read('config.cfg')


def config_reader(section):
    # XXX Do exception handling
    m = re.search('^funnel\.(.+)$', section)
    try:
        section = m.group(1)
    except AttributeError:
        log.error('%s is not a valid config section')
        sys.exit(1)

    class F:
        @classmethod
        def get(cls, x):
            global config
            return config.get(section, x)
    return F



