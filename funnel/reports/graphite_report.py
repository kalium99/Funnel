from funnel.connectors.graphite_connector import GraphiteConnection
from datetime import datetime
import logging
import time

now = datetime.now
server = None # This should be set from loader.py

def report(f):

    result_server = GraphiteConnection(server, port=2023) #This is the aggregator port
 
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
            result_server.send('beaker.load.error.%s 1 %d\n' % (instance.id, int(time.time())))
            return
            
        finish = now()
        response_time = (finish - start)
        result_server.send('beaker.load.response.%s %f %d\n' % (instance.id, response_time.total_seconds(), int(time.time())))
        result_server.send('beaker.load.hit.single.%s 1 %s\n' % (instance.id, int(time.time())))

    return the_run
