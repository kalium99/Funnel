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
from funnel.reports import graphite_report

import logging
log = logging.getLogger(__name__)

now = datetime.now

def _parser():
    parser = OptionParser('usage: %prog [options] --profile=PROFILE_FILE',
            description='Runs a load profile against a target server')
    parser.add_option('-l','--log', 
        help="sets log level")
    parser.add_option('-p','--profile', 
        help="sets load profile")
    return parser


def main():
    parser = _parser()

    (opts, args) = parser.parse_args()
    if not opts.log:
        opts.log = 'INFO'
    if not opts.profile:
        parser.error('Specify a load profile with --profile')
    lvl = getattr(logging, opts.log.upper(), logging.ERROR)
    logging.basicConfig(level=lvl)
    manager = LoadManager(opts.profile)
    manager.start()


class LoadManager(object):

    _last_session = {}

    def __init__(self,profile_file):
        self.start_time = now()
        self.agents = []
        self.profile = profile_file
        self._build_agents()

    def _build_agents(self):
        """Builds agents that generate load

        Agents control running of Sessions.
        Agents are a sub class of multipriocessing.Process
        """
        from request import RequestFactory, FAILED, PASSED, Request, LoadProcessor, get_rate_in_seconds, User
        from sessions.session import Session
        dom = etree.parse(self.profile)
        config = dom.xpath('//config')[0]
        config_options = {}
        for section in config.getchildren():
            # XXX use another function/class to do this work with a dispatch table or somehing
            if section.tag == 'baseload':
                if not section.get('unit'): # we aren't a rate
                    Session.baseload[section.get('session')] = section.get('requests')
                else: 
                    Session.baseload[section.get('session')] = \
                        get_rate_in_seconds(section.get('requests'), section.get('unit'))
            elif section.tag =='server':
                setattr(Request, section.tag, section.get('value', None))
            elif section.tag == 'xmlproxy':
                 setattr(Request, section.tag, section.get('value', None))
            elif section.tag == 'graphiteserver':
                setattr(graphite_report.GraphiteReport, 'server', section.get('value'))

        load_profile = dom.xpath('/root/load/user')
        for user in load_profile:
            processed_user = LoadProcessor.process(user)
            load_level = processed_user['load_level'] 
            session = processed_user['session']
            duration_minutes = processed_user['duration_minutes']
            delay = processed_user['delay'] 
            transition_time = processed_user['transition_time']
            run_once = processed_user['run_once']
            user_args = {}
            for arg in user.getchildren():
                if arg.tag == 'arg':
                    user_args.update(LoadProcessor.process(arg)) 
            agent = LoadAgent(User(duration_minutes, load_level, session, transition_time, user_args, run_once), delay)
            self.agents.append(agent)

    def start(self):
        """Run all LoadAgents
           
        Each LoadAgent runs as a sepereate Process and will generate 
        requests (load) upon the server,
        It will have it's own individual timing that duration that 
        it needs to adhere to (as dictated by the load.xml)

        """
        # start the agent threads
        for agent in self.agents:
            log.info('Starting new agent') #FIXME add in detail here
            agent.start()
        for agent in self.agents:
            agent.join()

class LoadAgent(Process):

    def __init__(self, user, delay=0):
        Process.__init__(self)
        self.user = user
        self.delay=delay

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
        while True:
            if expiration_time < now():
                break #We are finished
            run_thread = Thread(target=user_run)
            run_thread.setDaemon(False)
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
                break
            log.info('Waiting for  %s' % interval_seconds)
            sleep(interval_seconds)
                
    
class ResultWriter(Thread):
    def __init__(self, q, start_time):
        Thread.__init__(self)
        self.q = q
        self.start_time = start_time
    
    def run(self):
        f = open('results.csv', 'a')
        while True:
            q_tuple = self.q.get(True)
            trans_end_time, response_time, status, output = q_tuple
            elapsed = (trans_end_time - self.start_time)
            response_time_seconds = response_time.total_seconds()
            elapsed_seconds = elapsed.total_seconds()
            f.write('%.3f,%.3f,%s,%s\n' % (elapsed_seconds, response_time_seconds, status, output))
            f.flush()
            print '%.3f' % response_time_seconds


if __name__ == '__main__':
    main()
