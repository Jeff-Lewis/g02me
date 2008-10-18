from django.http import HttpResponse
from django.shortcuts import render_to_response

import threading
from urlparse import urlsplit, urlunsplit
import logging
import simplejson

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
    
class ReqFilter(object):
    """
    Setup global (thread local) variables for the request and handle exceptions thrown
    in the views.
    """
    def process_request(self, req):
        logging.info("request")
        local.stHost = "http://" + req.META["HTTP_HOST"] + "/"
        local.req = req
        
    def process_response(self, req, resp):
        logging.info("response")
        return resp
        
    def process_exception(self, req, e):
        logging.info("exception")
        if isinstance(e, DirectResponse):
            logging.info("Caught direct response")
            return e.resp
        if isinstance(e, Error):
            logging.info("Caught Error")
            return HttpError(req, e.obj['message'], obj=e.obj)

def HttpError(req, stError, obj={}):
    if req.has_key("callback"):
        if not 'status' in obj:
            obj['status'] = 'Fail'
        obj['message'] = stError
        logging.info('JSON Error: %(message)s (%(status)s)' % obj)
        return HttpJSON(req, obj=obj)
    logging.info('UI Error: %s' % stError)
    return render_to_response('error.html', {'strError' : stError})

class Error(Exception):
    def __init__(self, message, status='Fail', obj=None):
        if obj == None:
            obj = {}
        if not 'status' in obj:
            obj['status'] = status
        obj['message'] = message
        self.obj = obj
        
class DirectResponse(Exception):
    def __init__(self, resp):
        self.resp = resp
        
def RequireAdmin(req):
    user = RequireUser(req)
    if not users.is_current_user_admin():
        raise DirectResponse(HttpResponseRedirect(users.create_logout_url(req.get_full_path())))
    return user
    
def RequireUser(req):
    user = users.get_current_user()
    if not user:
        raise DirectResponse(HttpResponseRedirect(users.create_login_url(req.get_full_path())))
    return user
    
def RaiseNotFound(id):
    raise Error("The G02.ME page, http://g02.me/%s, does not exist" % id, obj={'id':id, 'status':'Fail/NotFound'})

def HttpJSON(req, obj={}):
    if not 'status' in obj:
        obj['status'] = 'OK'
    resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=JavaScriptEncoder)))
    # TODO: Set mime type
    return resp

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