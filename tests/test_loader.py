import unittest
import imp
from funnel.loader import LoadManager

class LoaderTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_process_profile(self):
        expected_details = {'profile4': ['0.0,1000.0,0,0:01:08.571429', '6000.0,1000.0,0,0:01:08.571429'],
                            'profile1': ['0.0,60.0,0,0:02:00', '1800.0,60.0,0,0:02:00'],
                            'profile3': ['0.0,5.0,0,0:13:20', '10.0,5.0,0,0:13:20'],
                            'profile2': ['0.0,20.0,0,0:00:02', '60.0,20.0,0,0:00:02']}
        imp.load_source('funnel.sessions.profile1', 'test_sessions/profile1.py')
        imp.load_source('funnel.sessions.profile2', 'test_sessions/profile2.py')
        imp.load_source('funnel.sessions.profile3', 'test_sessions/profile3.py')
        imp.load_source('funnel.sessions.profile4', 'test_sessions/profile4.py')
        profile = 'test-profile.xml'
        manager = LoadManager(profile)
        all_agent_details = {}
        # Each user from the profile will be represented by an agent
        for agent in manager.agents:
            delay = agent.delay
            user = agent.user
            session_id = user.session.id
            duration_minutes = user.duration_minutes
            transition_time = user.transition_time
            interval = user.interval
            try:
                session_string = "%s,%s,%s,%s" % (delay, duration_minutes,
                                  transition_time, interval)
                session_deets = all_agent_details[session_id]
            except KeyError:
                all_agent_details[session_id] = [session_string]
            else:
                session_deets.append(session_string)
        # Test that what what we have is what we expected to get
        import copy
        all_agent_details_copy = copy.deepcopy(all_agent_details)
        for session_id, details in all_agent_details_copy.items():
            for detail in details:
                expected_details[session_id].remove(detail)
                all_agent_details[session_id].remove(detail)
        expected_not_found = [v for k,v in expected_details.items() if v]
        unexpected_found = [v for k,v in all_agent_details.items() if v]
        #FIXME XXX What is the correct excpetion here to throw??
        if expected_not_found:
            self.AssertException('Expected entries not found %s' % expected_not_found)
        if unexpected_found:
            self.AssertException('Unexpected entries found %s' % expected_found)
