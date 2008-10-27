from google.appengine.api import users
from google.appengine.ext import db

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import loader, Context, Template

import settings

import threading
from urlparse import urlsplit, urlunsplit
import logging
import simplejson
from hashlib import sha1
import re

sIDChars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz-_"
nIDChars = len(sIDChars)

def IntToSID(i):
    # Convert int to "base 64" string - not compatible with Base64 string standard
    s = ''
    while i != 0:
        b = i % nIDChars
        s = sIDChars[b] + s
        i = i/nIDChars
    return s

def NormalizeUrl(url):
    url = url.strip()
    rgURL = list(urlsplit(url))
    if rgURL[0] == '':
        url = r"http://%s" % url
        rgURL = list(urlsplit(url))
    # Invalid protocol
    if rgURL[0] != "http" and rgURL[0] != "https":
        raise Error("Invalid protocol: %s" % rgURL[0]) 
    # Invalid domain
    if not rgURL[1]:        
        raise Error("Invalid URL: %s" % urlunsplit(rgURL))
    rgURL[1] = rgURL[1].lower()
    
    # Always end naked domains with a trailing slash as canonical
    if rgURL[2] == '':
        rgURL[2] = '/';
    return urlunsplit(rgURL)

def TrimString(st):
    if st == None:
        st = ''
    st = str(st)
    return st.strip()

def Slugify(s):
    "Converts to lowercase, removes non-alpha chars and converts spaces to hyphens"
    s = re.sub('[^\w\s-]', '', s).strip().lower()
    return re.sub('[-\s]+', '-', s)

from simplejson import JSONEncoder
from simplejson.encoder import Atomic
from datetime import datetime, timedelta

# --------------------------------------------------------------------
# JSON encoder helpers
# --------------------------------------------------------------------

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
        return 'new Date("%s")' % self.dt.strftime("%m/%d/%Y %H:%M GMT") 
    
class JavaScript(Atomic):
    def __init__(self, st):
        self.st = st;
        
    def __str__(self):
        return self.st;
    
# --------------------------------------------------------------------
# Django request filter middleware
# --------------------------------------------------------------------
    
class ReqFilter(object):
    """
    Setup global (thread local) variables for the request and handle exceptions thrown
    in the views.
    """
    asCookies =['userAuth', 'username']
    
    def process_request(self, req):
        import models

        host = req.META["HTTP_HOST"]

        # Enforce canonical URL's (w/o www)
        if host.startswith('www.'):
            return HttpResponseRedirect('http://%s%s' % (host[4:], req.path))
        
        # Initialize thread-local variables for this request
        local.req = req
        local.stHost = "http://" + host + "/"
        local.ipAddress = req.META['REMOTE_ADDR']
        
        # Copy the desired cookies into local.cookies dictionary
        local.cookies = {}
        for name in self.asCookies:
            local.cookies[name] = req.COOKIES.get(name, '')

        local.dtNow = datetime.now()
        local.sSecret = models.Globals.SGet(settings.sSecretName, "test server key")
        
    def process_response(self, req, resp):
        # If the user has no valid userAuth token, given them one for the next request
        try:
            RequireUserAuth()
        except:
            local.cookies['userAuth'] = SSign('au', SUserAuth())
            logging.info("new auth: %s" % local.cookies['userAuth'])

        for name in self.asCookies:
            if local.cookies[name] != '':
                resp.set_cookie(name, local.cookies[name], max_age=60*60*24*30)
            else:
                resp.delete_cookie(name)
        resp['Cache-Control'] = 'no-cache'
        resp['Expires'] = '0'
        return resp
        
    def process_exception(self, req, e):
        if isinstance(e, DirectResponse):
            return e.resp
        if isinstance(e, Error):
            return HttpError(req, e.obj['message'], obj=e.obj)
        logging.error("Uncaught exception")
        if not settings.DEBUG:
            return HttpError(req, "Application Error", {'status': 'Fail'})

# --------------------------------------------------------------------
# Response object for error reporting - handles JSON calls as well
# --------------------------------------------------------------------

def HttpError(req, stError, obj={}):
    if not 'status' in obj:
        obj['status'] = 'Fail'
    obj['message'] = stError
    if IsJSON():
        logging.info('JSON Error: %(message)s (%(status)s)' % obj)
        return HttpJSON(req, obj=obj)
    logging.info('UI Error: %s' % stError)

    http_status = 200
    if obj['status'] == 'Fail/NotFound':
        http_status = 404  
    t = loader.get_template('error.html')
    logging.info("Error: %r" % obj)
    resp = HttpResponse(t.render(Context(obj)))
    resp.status_code = http_status
    return resp

class Error(Exception):
    # Default Error exception
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
        
def RaiseNotFound(id):
    raise Error("The G02.ME page, http://g02.me/%s, does not exist" % id, obj={'id':id, 'status':'Fail/NotFound'})

def IsJSON():
    return local.req.has_key("callback")

def HttpJSON(req, obj={}):
    if not 'status' in obj:
        obj['status'] = 'OK'
    resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=JavaScriptEncoder)), mimetype="application/x-javascript")
    return resp
        
# --------------------------------------------------------------------
# Ensure user is signed in for request to procede
# --------------------------------------------------------------------
        
def RequireAdmin():
    user = RequireUser()
    if not users.is_current_user_admin():
        raise DirectResponse(HttpResponseRedirect(users.create_logout_url(local.req.get_full_path())))
    return user
    
def RequireUser():
    user = users.get_current_user()
    if not user:
        raise DirectResponse(HttpResponseRedirect(users.create_login_url(local.req.get_full_path())))
    return user

def RequireUserAuth():
    # Raises exception if fails
    s = SGetSigned('ua', local.cookies['userAuth'])
    return s

def SUserAuth():
    return "%s~%s" % (local.ipAddress, local.dtNow.strftime('%m/%d/%Y %H:%M'))
    
def RunInTransaction(func):
    # Function decorator to wrap entire function in an App Engine transaction
    def _transaction(*args, **kwargs):
        return db.run_in_transaction(func, *args, **kwargs)
    return _transaction

# --------------------------------------------------------------------
# String utilities - format date as an "age"
# --------------------------------------------------------------------

def SAgeReq(dt):
    # Return the age (time between time of request and a date) as a string
    return SAgeDdt(local.dtNow - dt)

def SAgeDdt(ddt):
    if ddt.days < 0:
        return "future?"
    months = int(ddt.days*12/365)
    years = int(ddt.days/365)
    if years >= 1:
        return "%d year%s ago" % (years, SPlural(years))
    if months >= 3:
        return "%d months ago" % months 
    if ddt.days == 1:
        return "yesterday"
    if ddt.days > 1:
        return "%d days ago" % ddt.days
    hrs = int(ddt.seconds/60/60)
    if hrs >= 1:
        return "%d hour%s ago" % (hrs, SPlural(hrs))
    minutes = round(ddt.seconds/60)
    if minutes < 1:
        return "seconds ago"
    return "%d minute%s ago" % (minutes, SPlural(minutes))

def SPlural(n, sPlural="s", sSingle=''):
    return [sSingle, sPlural][n!=1]

# --------------------------------------------------------------------
# Signed and verified strings can only come from the server
# --------------------------------------------------------------------

def SSign(type, s):
    # Sign the string using the server secret key
    # type is a short string that is used to distinguish one type of signed content vs. another
    # (e.g. user auth from).
    hash = sha1('~'.join((type, s, local.sSecret))).hexdigest().upper()
    return '~'.join((type, s, hash))

regSigned = re.compile(r"^(\w+)~(.*)~[0-9A-F]{40}$")

def SGetSigned(type, s, sError="Failed authentication"):
    # Raise exception if s is not a valid signed string of the correct type.  Returns
    # original (unsigned) string if succeeds.
    m = regSigned.match(s)
    try:
        if SSign(m.group(1), m.group(2)) == s:
            return m.group(2)
    except:
        pass
    raise Error(sError, 'Fail/Auth')

# --------------------------------------------------------------------
# Per-request global variables stored in this thread-local global
# --------------------------------------------------------------------
local = threading.local()
