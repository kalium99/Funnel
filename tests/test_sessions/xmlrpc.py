from funnel.request import RequestFactory
from funnel.sessions.session import Session as ParentSession
from funnel.reports import report

class Session(ParentSession):

    id = 'xmlrpc'

    def __init__(self, *args, **kw):
        super(Session, self).__init__(*args, **kw)
        method = 'parrot'
        method_args = ['squawk']
        self.request = RequestFactory.create('xmlrpc',
            method, method_args, keep_return=True)

    @report
    def run(self):
        result =  self.request.run()

