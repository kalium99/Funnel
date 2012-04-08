import subprocess
import random
import re
import xmlrpclib
import jsonrpclib
import logging
import time
import itertools
import errno
import Queue
from multiprocessing import Manager
from datetime import datetime, timedelta
from funnel.loader import LoadManager
from copy import copy
from time import sleep

log = logging.getLogger('funnel')
log.setLevel(logging.DEBUG)

now = datetime.now
FAILED = 'fail'
PASSED = 'pass'
def get_in_minutes(number, unit):
    if unit == 'minute':
        return float(number)
    if unit =='hour':
        return float(number) * 60
    if unit == 'second':
        return float(number) / 60.0

def get_in_seconds(number, unit):
    if unit == 'second':
        return float(number)
    if unit == 'minute':
        return float(number) * 60
    if unit == 'hour':
        return float(number) * 3600

def get_rate_in_seconds(number, unit):
    if unit == 'second':
        return float(number)
    if unit == 'minute':
        return 60 / float(number) 
    if unit == 'hour':
        return 3600 / float(number)

    
class RequestFactory(object):

    @classmethod
    def create(cls, type, *args, **kw):
        req = None
        # XXX move this out to a request dir where each class is a module
        if type == 'xmlrpc':
            req = XMLRPCRequest(*args, **kw) 
        if type == 'jsonrpc':
            req = JSONRPCRequest(*args, **kw)
        if type == 'http':
            req = HTTPRequest(*args, **kw)
        if type == 'qpid':
            req = QPIDRequest(*args, **kw)
        if type == 'client':
            req = ClientRequest(*args, **kw)
        if req is None:
            raise ValueException('% is not a value Request type' % type)
        class_name = req.__class__.__name__
        return req

class Request(object):
 
    def __init__(self, keep_return=False, id=None, share=None, *args, **kw):
        self.keep_return = keep_return
        self.id = id
        #self.result_queue = share

    def cleanup(self):
        pass

    def run(self, *args, **kw):
        """Prepare and execute hit on server

        run is responsible for implementing the details of how to generate an individual
        hit on a server.
        """

        raise NotImplementedError('Subclasses or Request must define their own run() method')

        
class ClientRequest(Request):
    
    result_queue = Manager().dict()
    process_queue = Queue.Queue()
  
    def __init__(self, cmd, args=None,  keep_return=False, *a, **kw):
        super(ClientRequest, self).__init__(*a, **kw)
        self.cmd = cmd
        self.keep_return = keep_return
        self.cmd = self.cmd.split(" ") 
        self.args = args or []

    def cleanup(self):
        log.debug('In ClientRequest.cleanup')
        while True:
            try:
                p = self.process_queue.get(False)
            except Queue.Empty:
                break
            try:
                p.terminate()
                log.debug('Terminated process')
            except OSError, e:
                if e.errno == errno.ESRCH: #No Such Process
                    pass
                else:
                    raise

    def run(self):
        runnable_cmd = copy(self.cmd)
        for arg in self.args:
            if callable(arg):
                arg = arg()
            runnable_cmd.append(arg)
        log.debug('Running %s' % runnable_cmd)
        # FIXME piping stdout to screen should be removed beyond testing
        self.p = subprocess.Popen(runnable_cmd, stdout=subprocess.PIPE, close_fds=True)
        self.process_queue.put(self.p)
        stdout, stderr = self.p.communicate() 
        if stderr:
            log.debug('Stderr: %s' % stderr)
        if self.keep_return:
            if self.id in self.result_queue:
                q_ = self.result_queue[self.id]
                q_.append(stdout)
                self.result_queue[self.id] = q_
            else:
                self.result_queue[self.id] = [stdout]
        log.debug('Returning from ClientRequest')
        if stderr:
            # FIXME record error
            return FAILED, stderr
        else:
            return PASSED, stdout

class HTTPRequest(Request):

    def __init__(self, *args, **kw):
        super(HTTPRequest, self).__init__(*args, **kw)

class XMLRPCRequest(HTTPRequest):

    result_queue = Manager().dict()

    def __init__(self, method, method_args, *args, **kw):
        super(XMLRPCRequest, self).__init__(*args, **kw)
        self.method = method
        self.method_args = method_args
        self.headers = {'Content-Type' : 'text/xml'}

    def run(self):
        # FIXME do exception handling and params
        self.rpc = xmlrpclib.ServerProxy(self.server + self.xmlproxy, allow_none=True)
        for prop in self.method.split("."):
            self.rpc = getattr(self.rpc, prop)
        response = self.rpc(*self.method_args) 
        return PASSED, response #FIXME need to check for errors

class JSONRPCRequest(HTTPRequest):

    result_queue = Manager().dict()

    def __init__(self, method, method_args, param=None, *args, **kw):
        super(JSONRPCRequest, self).__init__(*args, **kw)
        self.method = method
        self.headers = {'Content-Type' : 'application/json-rpc'}
        self.method_args = method_args
       
    def run(self):
        # FIXME do exception handling and params
        self.rpc = jsonrpclib.ServerProxy(self.server + self.xmlproxy, allow_none=True)
        for prop in self.method.split("."):
            self.rpc = getattr(self.rpc, prop)
        response = self.rpc(*self.method_args) 
        return PASSED, response #FIXME need to check for errors


class LoadProcessor:


    """
    LoadProcessor takes elements from the load.xml and returns the data
    we care about in a form we can deal with
    """

    _valid_time_units = {'minute' : 1,
                         'second' : 1,
                         'hour' : 1, }

    def __init__(self, *agrs, **kw):
        pass

    @classmethod
    def process(cls, element):
        f = getattr(cls, 'process_%s' % element.tag, None)
        if f is None:
            raise ValueError('%s is not a recognised load element' % element.tag)
        else:
            return f(element)

    @classmethod
    def _process_var(cls, element):
        var_name = element.get('name')
        var_val = element.text
        return {var_name : var_val}

    @classmethod
    def process_vars(cls, element):
        # Get vars and load them into a dict in the session class  
        session = element.get('session')
        if not session:
            raise ValueError('vars needs a session')
        vars_ = {}
        for var in element.getchildren():
            if var.tag != 'var':
                raise ValueError # XXX make this better
            vars_.update(cls._process_var(var))
        return { session : vars_ }

    @classmethod
    def process_user(cls, user):
        time_unit = user.get('unit')
        if time_unit not in cls._valid_time_units:
            raise ValueError('%s is not a valid time unit. Please use one of %s' % ( time_unit, ','.join(cls._valid_time_units.keys())))
        user_deets = {}
        # XXX Do error checking here
        run_once = user.get('run_once')
        user_deets['run_once'] = user.get('run-once')
        user_deets['load_level'] = user.get('load-level')
        user_deets['session'] = user.get('session')
        user_deets['duration_minutes'] = get_in_minutes(user.get('duration'), time_unit)
        transition = user.get('transition')
        if transition is not None:
            transition = re.sub('%','', transition)
            transition_multiplier = float(transition) / 100.0
            transition_time_seconds = transition_multiplier * get_in_seconds(user_deets['duration_minutes'], 'minute')
            user_deets['transition_time'] = transition_time_seconds
        else:
            user_deets['transition_time'] = 0
        delay = user.get('delay', 0)
        user_deets['delay'] = get_in_seconds(delay, time_unit)
        return user_deets

    @classmethod
    def process_request(cls, request):
        request_deets = {}
        #equest_attributes = dict(request.items())
        request_deets['type'] = request.get('type')
        request_deets['interval_seconds'] = get_in_seconds(
            float(request.get('interval')), request.get('unit'))
        request_deets.update(dict([(k,v) for k,v in request.items() if k not in ['type', 'interval', 'unit']]))
        return request_deets

    @classmethod
    def process_param(cls, param):
        param_deets = {}
        param_deets[param.get('name')] = param.get('value')
        return param_deets

    @classmethod
    def process_arg(cls, arg):
        return { arg.get('name') : arg.get('value') }


class User:

    data_share = Manager().dict()

    def __init__(self, duration_minutes, load_level, session_name,
        transition_time, session_args, session_baseload, run_once):
        self.duration_minutes = duration_minutes
        self.session = SessionFactory.create(session_name)(self.data_share, session_args, session_baseload)
        self.transition_time = transition_time
        if load_level == 'x': # if we want to blitz the server
            self.interval = timedelta(seconds=0.01) # Try not to overwhelm the host machine
        elif run_once:
            # For run once timings we pass on the load_level to the session so it can do timing if it wishes to
            self.session.load_level = float(load_level)
            self.interval = None
        else:
            # XXX do try/except for division errors
            self.interval = timedelta(seconds=self.session.baseload / float(load_level))

    def __str__(self):
        return '%s:%s' % (self.session.__class__.__module__, self.duration_minutes)

    def cleanup(self):
        log.debug('In User cleanup')
        self.session.cleanup()
 
    def run(self):
        result = self.session.run()
        log.debug('Returning from User') 
        return result

class SessionFactory(object):

    @classmethod
    def create(cls, session_name):
        session_ref = __import__('funnel.sessions.%s' % session_name, {}, {}, [session_name])
        if session_ref is None:
            raise ValueError('%s is not a valid session' % session_name)

        def f(*args):
            return session_ref.Session(session_name, *args)
        return f
