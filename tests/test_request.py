from funnel.request import RequestFactory, HTTPRequest
import unittest


class TestRequest(unittest.TestCase):


    def test_factory(self):
        http_req = RequestFactory.create('http')
        self.assert_(http_req.__class__ is HTTPRequest) 
