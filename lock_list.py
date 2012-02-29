"""
Locking and thread safe list
"""
from threading import RLock

class lockList:
    """
    lockList behaves like a list but acquires a thread lock before
    setting, getting, or deleting items.  Additionally, the
    RLock.acquire() and release() methods are preserved to see if the list
    is currently locked.
    """
    def __init__(self, init=None):
        if not type(init) == list:
            self.list = []
        else:
            self.list = init
        self.rlock = RLock()
    def __len__(self):
        return len(self.list)
    def __getitem__(self, key):
        self.rlock.acquire()
        value = self.list[key]
        self.release()
        return value
    def __setitem__(self, key, value):
        self.rlock.acquire()
        self.list[key] = value
        self.rlock.release()
    def __delitem__(self, key):
        self.rlock.acquire()
        del self.list[key]
        self.rlock.release()
        return value
    def __contains__(self, item):
        self.rlock.acquire()
        retval = item in self.list
        self.rlock.release()
        return retval
    def remove(self, l):
        self.rlock.acquire()
        self.list.remove(l)
        self.rlock.release()
    def pop(self, *parameters):
        self.rlock.acquire()
        retval = self.list.pop(*parameters)
        self.rlock.release()
        return retval
    def append(self, l):
        self.rlock.acquire()
        self.list.append(l)
        self.rlock.release()
    def __iter__(self):
        self.rlock.acquire()
        retval = list.__iter__(self.list)
        self.rlock.release()
        return retval
    def __reversed__(self):
        self.rlock.acquire()
        retval = list.__reversed__(self.list)
        self.rlock.release()
        return retval
    def __add__(self, other):
        self.rlock.acquire()
        retval = self.list + other
        self.rlock.release()
        return retval
    def __radd__(self, other):
        self.rlock.acquire()
        retval = other + self.list
        self.rlock.release()
        return retval
    def acquire(self, block=1):
        return self.rlock.acquire(block)
    def release(self):
        self.rlock.release()
