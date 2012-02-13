try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    from pkgutil import extend_path
    __path__ = extend_path(__path__, __name__)
from datetime import datetime
import time
import logging

log = logging.getLogger(__name__)

_plugins = []
_now = datetime.now

def enable_report_plugin(plugin_obj):
    _plugins.append(plugin_obj)
   
def report(f):
    """
    reporter() should be the only wrapper for functions which are to be reported on
    each time it makes a run it checks all the report_handlers and passes
    to them the data in a standard format.
    """

    def the_run(instance, *args):
        """Sends data to graphite server
        sends error count, hit count, and response times
        """
        start = _now() 
        try:
            # XXX result and output currently not used...
            result, output = f(instance, *args)
        except Exception, e:
            log.exception(e)
            for handle in _plugins:
                handle.report_failure(instance.id, int(time.time()))
            return    
        finish = _now()
        response_time = (finish - start)
        for handle in _plugins:
            handle.report_success(instance.id, response_time, int(time.time()))
    return the_run
        
