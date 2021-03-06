from time import sleep
from datetime import datetime, timedelta
import sys
import os
import re
import httplib
import logging
from optparse import OptionParser
from threading import Thread
from multiprocessing import Process, Queue, Manager
import ConfigParser
from lxml import etree
from funnel.reports import graphite_report #This should monkey patch itself in
from funnel.reports import local_report
from funnel import startup

import logging
log = logging.getLogger('funnel')

now = datetime.now

def _parser():
    parser = OptionParser('usage: %prog [options]',
            description='Runs a load profile against a target server')
    parser.add_option('-l','--log', 
        help="sets log level")
    parser.add_option('-p','--profile', 
        help="sets load profile")
    parser.add_option('-s','--load-server', 
        help="the server to be targeted")
    parser.add_option('-g','--graphite-server', 
        help="If using graphite, the server to send results to")
    parser.add_option('-c','--ssl', 
        action="store_true",
        help="If your target server is setup for ssl, then use this option")
    parser.add_option('-r','--report', action='append', dest='reports',
        help="The type of reporting to use")
    return parser


def main():
    parser = _parser()

    (opts, args) = parser.parse_args()
    if not opts.log:
        opts.log = 'INFO'
    if not opts.profile:
        parser.error('Specify a load profile with --profile')
    load_server = opts.load_server
    ssl = opts.ssl
    lvl = getattr(logging, opts.log.upper(), logging.ERROR)
    logging.basicConfig(level=lvl)

    # Anything that needs to be done before we run our load
    # should be appended to funnel.startup.call_on_startup,
    # and will be called by do_startup()
    startup.do_startup()
    manager = LoadManager(opts.profile, load_server=load_server,
        ssl=ssl)
    manager.start()


class LoadManager(object):

    _last_session = {}

    def __init__(self,profile_file, load_server=None, ssl=False):
        self.start_time = now()
        self.agents = []
        self.profile = profile_file
        self.load_server = load_server
        self.ssl = ssl
        self._build_agents()

    def _build_agents(self):
        """Builds agents that generate load

        Agents control running of Sessions.
        Agents are a sub class of multiprocessing.Process
        """
        from request import RequestFactory, FAILED, PASSED, Request, LoadProcessor, get_rate_in_seconds, User
        from sessions.session import Session
        dom = etree.parse(self.profile)
        config = dom.xpath('//config')[0]
        config_options = {}
        if self.ssl:
            server_proto = 'https'
        else:
            server_proto = 'http'
        Request.server = '%s://%s' % (server_proto, self.load_server)
        session_vars = {}
        session_baseload = {}
        for section in config.getchildren():
            # XXX TODO use another function/class to do this work with a dispatch table or somehing
            if section.tag == 'baseload':
                if not section.get('unit'): # we aren't a rate
                    session_baseload[section.get('session')] = section.get('requests')
                else:
                    session_baseload[section.get('session')] = \
                        get_rate_in_seconds(section.get('requests'), section.get('unit'))
            elif section.tag =='server' and not Request.server:
                setattr(Request, section.tag, section.get('value', None))
            elif section.tag == 'xmlproxy':
                 setattr(Request, section.tag, section.get('value', None))
            elif section.tag == 'vars':
                session_vars.update(LoadProcessor.process(section))

        load_profile = dom.xpath('/root/load/user')
        for user in load_profile:
            processed_user = LoadProcessor.process(user)
            load_level = processed_user['load_level']
            session = processed_user['session']
            duration_minutes = processed_user['duration_minutes']
            delay = processed_user['delay']
            transition_time = processed_user['transition_time']
            run_once = processed_user['run_once']
            # XXX TODO Make it so we can load per user session_vars
            agent = LoadAgent(User(duration_minutes, load_level, session,
                                   transition_time, session_vars.get(session),
                                   session_baseload.get(session),
                                   run_once), delay)
            self.agents.append(agent)

    def start(self):
        """Run all LoadAgents

        Each LoadAgent runs as a sepereate Process and will generate 
        requests (load) upon the server,
        It will have it's own individual timing that duration that 
        it needs to adhere to (as dictated by the load.xml)

        """
        # start the agent Process
        for agent in self.agents:
            log.info('Starting agent: %s' % agent) #FIXME add in detail here
            agent.start()
        for agent in self.agents:
            agent.join()

class LoadAgent(Process):

    def __init__(self, user, delay=0):
        Process.__init__(self)
        self.user = user
        self.delay=delay

    def __str__(self):
        return str(self.user)

    def _transition_closure(self, start_time, transition_time, transition_target_interval):
 
         finish_transition_time = start_time + timedelta(seconds=transition_time)

         def f(current_interval):

            """Returns the latest interval timing needed in the transition process

                start_time: this is the time at which the LoadAgent begins
                transition_time: this is the length of time it will take for the transition
                process to complete
                transition_target_interval: This is the rate we want to transition to.
                current_interval: This is our current_interval
        
                Say we start with the following:
                start_time = 1:00
                transition_time = 10
                transition_target_interval = 2.0
                current_interval = 1.0
        
                To figure out our next transitioning interval:
                next_interval = (transition_target_interval - current_interval) / transition_time +- current_interval
                next_interval = (2.0- 1.0)/10 +- 1.0
                Thus next_interval = 1.1
                
                The the next time our function is called, our values will likely be:
                transition_time = finish_transition_time - current_time
                current_interval = 1.1
                next_interval = (2.0 - 1.1) / 8.9 +- 1.1
                Thus next_interval = 1.201

            """
            transition_time = (finish_transition_time - now()).total_seconds()
            if transition_time < transition_target_interval: # We're close enough to our transition target
                return transition_target_interval 
            return (transition_target_interval - current_interval) / transition_time + current_interval
         return f  

    def cleanup(self):
        log.debug('In LoadAgent.cleanup')
        self.user.cleanup()
                   
    def run(self):
        """Runs individual request/hit as thread

        Keeps track of duration and timing interval to ensure that
        requests are generated according to expectexd request hit rate and
        duration.
        """
        # expiration time might be milliseconds behind expected due to start being
        # a different value
        if self.user.interval is not None:
            get_interval_seconds = self.user.interval.total_seconds
            interval_seconds = get_interval_seconds()
            transition_time = self.user.transition_time
        else:
            interval_seconds = None
            transition_time = False
        log.info('Delaying for %s' % self.delay)
        sleep(self.delay)
        current_time = now()
        expiration_time = current_time + timedelta(minutes=self.user.duration_minutes)
        current_interval = interval_seconds
        if transition_time:
            transitioning = True
            previous_interval =  self.user.session.previous_interval
            get_transition_interval = self._transition_closure(current_time, transition_time, current_interval)
            interval_seconds = previous_interval
        else:
            transitioning = False
        self.user.session.set_previous_interval(current_interval)
        user_run = self.user.run
        self.user_threads = []
        try:
            while True:
                if expiration_time < now():
                    log.debug('Exiting agent %s' % self)
                    break #We are finished
                run_thread = Thread(target=user_run)
                run_thread.setDaemon(True)
                self.user_threads.append(run_thread)
                while True:
                    try:
                        run_thread.start()
                        break
                    except: #perhaps we have created too many threads
                        sleep(0.1)
                        continue
                if transitioning:
                    interval_seconds = get_transition_interval(interval_seconds)
                    if interval_seconds == get_interval_seconds():
                        transitioning = False
                if interval_seconds is None: #this should only be set by run_once
                    # When we have no interval, we need to control the duration here
                    sleep(timedelta(minutes=self.user.duration_minutes).total_seconds())
                    log.debug('Exiting agent %s' % self)
                    break
                log.info('Waiting for  %s' % interval_seconds)
                sleep(interval_seconds)
        finally:
            for t in self.user_threads:
                t.join()
            self.cleanup()
            sys.exit()

def run_main(**kw):
    """
    run_main is desined to test funnel by passing options as **kwargs
    rather than pasing them in the shell and having them dissected by the
    opts parser. Useful for testing!
    """
    # XXX We should be able to decouple the logic from test_main() and main()
    # and have light wrappers for each
    if 'load_server' in kw:
        load_server = kw['load_server']
    if 'profile' in kw:
        profile = kw['profile']
    if 'graphite_server' in kw:
        graphite_server = kw['graphite_server']
    if 'log' in kw:
        log = kw['log']
    else:
        log = 'INFO'

    if 'ssl' in kw:
        ssl = kw['ssl']
    else:
        ssl = False

    lvl = getattr(logging, log.upper(), logging.ERROR)
    logging.basicConfig(level=lvl)
    manager = LoadManager(profile, load_server=load_server, 
        ssl=ssl)
    startup.do_startup()
    manager.start()
 
if __name__ == '__main__':
    main()
