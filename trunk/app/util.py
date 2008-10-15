import threading
from urlparse import urlsplit, urlunsplit
import logging

s64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
def IntToS64(i):
    # Convert int to "base 64" string - not compatible with Base64 string standard
    s = []
    while i != 0:
        b = i % 64
        s = [s64[b]] + s
        i = i/64
    return ''.join(s)

def NormalizeUrl(url):
    url = url.strip()
    rgURL = urlsplit(url)
    if rgURL[0] == '':
        url = r"http://%s" % url
        rgURL = urlsplit(url)
    if rgURL[0] != "http" and rgURL[0] != "https":
        foo = Error("Invalid protocol: %s" % rgURL[0], "Fail/Foo")
        bar = Error("Invalid protocol: %s" % rgURL[0])
        raise bar 
    if not rgURL[1]:        
        raise Error("Invalid URL: %s" % urlunsplit(rgURL))
    return urlunsplit(rgURL)

def TrimString(st):
    if st == None:
        st = ''
    st = str(st)
    return st.strip()

from simplejson import JSONEncoder
from simplejson.encoder import Atomic
from datetime import datetime

class JavaScriptEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return JSDate(obj)
        return JSONEncoder.default(self, obj)
    
class JSDate(Atomic):
    def __init__(self, dt):
        self.dt = dt
        
    def __str__(self):
        # new Date("10/4/2008 19:54 GMT")
        return 'new Date("%d/%d/%4d %2d:%2d GMT")' % (
              self.dt.month, self.dt.day, self.dt.year, self.dt.hour, self.dt.minute
              ) 
    
class JavaScript(Atomic):
    def __init__(self, st):
        self.st = st;
        
    def __str__(self):
        return self.st;
    
class Error(Exception):
    def __init__(self, message, status='Fail', obj=None):
        if obj == None:
            obj = {}
        if not 'status' in obj:
            obj['status'] = status
        obj['message'] = message
        self.obj = obj

# Global strings
sISO = "PF.ISO.ToDate(\"%sZ\")"

# Save request info in a thread-global
local = threading.local()

import unittest

class TestIntToS64(unittest.TestCase):
    def test(self):
        i = 1
        for ch in s64[1:]:
            self.assertEqual(IntToS64(i), ch)
            i = i + 1
        self.assertEqual(IntToS64(64), "10")
        self.assertEqual(IntToS64(64*64+10), "10A")
        print 64 ** 5
        self.assertEqual(IntToS64(64 ** 5), "100000")
        
class TestNormalizeUrl(unittest.TestCase):
    def test(self):
        self.assertEqual(NormalizeUrl("http://hello"), "http://hello")
        self.assertEqual(NormalizeUrl("  http://hello  "), "http://hello")

if __name__ == '__main__':
  unittest.main()