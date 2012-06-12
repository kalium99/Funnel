from funnel.request import RequestFactory, FAILED, PASSED
from funnel.sessions.session import Session as ParentSession
from funnel.reports import report

class Session(ParentSession):

    id = 'profile2'


