from funnel.connectors.graphite_connector import GraphiteConnection
from funnel.startup import call_on_startup
from funnel.reports import enable_report_plugin
from funnel.config import config_reader
from datetime import datetime
import logging
import time
import sys

config = config_reader('reports.graphite_report')
log = logging.getLogger(__name__)
_now = datetime.utcnow
_date_prefix = _now().strftime('%Y%m%d')

def report_event(target, val=1):
    if not target:
        raise ValueError('Must specify a proper target namespace')
    GraphiteReport().result_server.send('%s.%s %d %s\n' % (_date_prefix, target, val, int(time.time())))

class GraphiteReport:
    try:
        server = config.get('server')
    except KeyError:
        log.error('No server specified for graphite report plugin')
        sys.exit(1)

    try:
        port = config.get('port')
    except KeyError:
        log.error('No port specified for graphite server, try \
            2023 for aggregate or 2003 for regular')
        sys.exit(1)

    def __init__(self, *args, **kw):
        self.result_server = GraphiteConnection(self.server, port=self.port) #This is the aggregator port

    def report_success(self, id, response_time, current_timestamp):
        self.result_server.send('%s.beaker.load.response.%s %f %d\n' % (_date_prefix, id, response_time.total_seconds(), current_timestamp))
        self.result_server.send('%s.beaker.load.hit.single.%s 1 %s\n' % (_date_prefix, id, current_timestamp))

    def report_failure(self, id, current_timestamp):
        self.result_server.send('%s.beaker.load.error.%s 1 %d\n' % (_date_prefix,id, current_timestamp))

def add_graphite_report_plugin():
    if config.get('disabled'):
        log.info('Disabling graphite plugin')
    else:
        log.info('Enabling graphite plugin')
        enable_report_plugin(GraphiteReport())

call_on_startup.append(add_graphite_report_plugin)
