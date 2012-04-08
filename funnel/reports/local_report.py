import logging
import time
import sys
import logging
from datetime import datetime
from funnel.startup import call_on_startup
from funnel.reports import enable_report_plugin
from funnel.config import config_reader

config = config_reader('reports.local_report')
log = logging.getLogger(__name__)
now = datetime.now
error_file = config.get('error_log')
results_file = config.get('results_file')
error_file = '%s_%s.csv' % (error_file, time.strftime('%Y%m%d%H%M'))
results_file = '%s_%s.csv' % (results_file, time.strftime('%Y%m%d%H%M'))


class LocalReport:

    def __init__(self, *args, **kw):
        self.results = open(results_file, 'wb')
        self.error = open(error_file, 'wb')

    def report_success(self, id, response_time, current_timestamp):
        self.results.write('%s %s %s\n' % (id, response_time, current_timestamp))
        self.results.flush()

    def report_failure(self, id, current_timestamp):
        self.error.write('%s %s\n' % (id, current_timestamp))
        self.error.flush()

def add_local_report_plugin():
    log.info('Enabling local report plugin')
    enable_report_plugin(LocalReport())

call_on_startup.append(add_local_report_plugin)
