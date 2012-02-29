"""
Locking and thread safe dictionary
"""
from threading import RLock

class lockDict:
    """
        lockDict behaves like a dictionary but acquires a thread lock before
        setting, getting, or deleting items.  Additionally, the
        RLock.acquire() and release() methods are preserved to see if the
        dictionary is currently locked.
    """
    def __init__(self, init=None):
        if not type(init) == dict:
            self.dict = {}
        else:
            self.dict = init
        self.rlock = RLock()
    def __len__(self):
        return len(self.dict)
    def __getitem__(self, key):
        self.rlock.acquire()
        value = self.dict[key]
        self.rlock.release()
        return value
    def __setitem__(self, key, value):
        self.rlock.acquire()
        self.dict[key] = value
        self.rlock.release()
    def __delitem__(self, key):
        self.rlock.acquire()
        del self.dict[key]
        self.rlock.release()
    def __contains__(self, item):
        self.rlock.acquire()
        retval = item in self.dict
        self.rlock.release()
        return retval
    def __iter__(self):
        self.rlock.acquire()
        retval = dict.__iter__(self.dict)
        self.rlock.release()
        return retval
    def get(self, key):
        self.rlock.acquire()
        retval = self.dict.get(key)
        self.rlock.release()
        return retval
    def acquire(self, block=1):
        return self.rlock.acquire(block)
    def release(self):
        self.rlock.release()
