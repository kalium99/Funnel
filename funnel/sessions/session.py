from multiprocessing import Manager

class Session(object):

    baseload = {}
    _previous_user = None
    request_share = Manager().dict()
        
    def __init__(self, name, share, s_args, baseload, *args, **kw):
        self.name = name
        self._previous_user = share
        self.s_args = s_args
        self.baseload = baseload
            
    @property
    def previous_interval(self):
        return self._previous_user.get(self.id, 0)

    def cleanup(self):
        pass

    def set_previous_interval(self,val):
        self._previous_user[self.id] = val
 
