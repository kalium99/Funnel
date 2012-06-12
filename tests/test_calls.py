import sys
import imp
import os
import unittest
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from threading import Thread
from funnel.loader import run_main
from funnel.reports import local_report

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

def parrot(arg):
    return arg

class TestCalls(unittest.TestCase):

    @classmethod
    def setupClass(cls):
        server = SimpleXMLRPCServer(('localhost', 8080), requestHandler=RequestHandler)
        server.register_function(parrot)
        cls.t = Thread(target=server.serve_forever)
        cls.t.daemon = True
        cls.t.start()

    @classmethod
    def teardownClass(cls):
        pass

    def test_xmlrpc_calls(self):
        imp.load_source('funnel.sessions.xmlrpc', 'test_sessions/xmlrpc.py')
        run_main(profile='test-calls.xml', load_server='localhost:8080')
        try:
            open(local_report.results_file)
        except IOError:
            self.fail('Could not open results file %s, \
                perhaps test did not finish properly ' % local_report.results_file)
