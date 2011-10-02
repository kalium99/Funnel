from funnel.connectors.graphite_connector import GraphiteConnection
from datetime import datetime
import logging
import time

now = datetime.now
date_prefix = now().strftime('%Y%m%d')

class GraphiteReport:

    server = None # This should be set from loader.py

    @classmethod
    def result_server(cls):
        return GraphiteConnection(cls.server, port=2023) #This is the aggregator port

def report_event(target, val=1):
    if not target:
        raise ValueError('Must specify a proper target namespace')
	
    GraphiteReport.result_server().send('%s.%s %d %s\n' % (date_prefix, target, val, int(time.time())))

def report(f):
    result_server = GraphiteReport.result_server()
 
    def the_run(instance, *args):
        """Sends data to graphite server
        sends error count, hit count, and response times
        """
        start = now() 
        try:
            # XXX result and output currently not used...
            result, output = f(instance, *args)
        except Exception, e:
            logging.exception(e)
            result_server.send('%s.beaker.load.error.%s 1 %d\n' % (date_prefix,instance.id, int(time.time())))
            return
            
        finish = now()
        response_time = (finish - start)
        result_server.send('%s.beaker.load.response.%s %f %d\n' % (date_prefix, instance.id, response_time.total_seconds(), int(time.time())))
        result_server.send('%s.beaker.load.hit.single.%s 1 %s\n' % (date_prefix, instance.id, int(time.time())))

    return the_run
