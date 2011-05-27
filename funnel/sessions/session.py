from multiprocessing import Manager

class Session(object):

    baseload = {}
    _previous_user = None
    request_share = Manager().dict()
        
    def __init__(self, share, session_args, *args, **kw):
        self._previous_user = share
        self.session_args = session_args
            
    @property
    def previous_interval(self):
        return self._previous_user.get(self.id, 0)

    def set_previous_interval(self,val):
        self._previous_user[self.id] = val
 
