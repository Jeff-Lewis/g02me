from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import db


from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import loader, Context, Template

import settings
from timescore.models import MemRate

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

def Href(url):
    ich = url.find('//')
    path = url[ich+2:].replace('"', '%22')
    return url[0:ich+2] + path

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
        local.mpResponse = {}
        local.requser = ReqUser(req)
        
    def process_response(self, req, resp):
        # If the user has no valid userAuth token, given them one for the next request
        try:
            RequireUserAuth(True)
        except:
            local.cookies['userAuth'] = SSign('au', SUserAuth())
            logging.info("new auth: %s" % local.cookies['userAuth'])

        for name in self.asCookies:
            if local.cookies[name] != '':
                resp.set_cookie(name, local.cookies[name], max_age=60*60*24*30)
            else:
                resp.delete_cookie(name)
        # TODO: Should allow client caching of home and /tag pages - 60 seconds
        resp['Cache-Control'] = 'no-cache'
        resp['Expires'] = '0'
        return resp
        
    def process_exception(self, req, e):
        if isinstance(e, DirectResponse):
            return e.resp
        if isinstance(e, Error):
            return HttpError(req, e.obj['message'], obj=e.obj)
        # TODO - write exception backtrace into log file
        logging.error("Uncaught exception")
        if not settings.DEBUG:
            return HttpError(req, "Application Error", {'status': 'Fail'})
        
class ReqUser(object):
    """
    Permissions:
        'view': Can view (read-only) data from site
        'view-count': Can update view counts
        'share': Can share new url's
        'comment': Can comment (or delete comments) on url's
        'admin': Can use admin page
    """
    mpPermMessage = {}
    mpPermError = {}

    def __init__(self, req):
        # Nothing allowed by default!
        self.req = req
        self.mpAllowed = set()

        self.ip = req.META['REMOTE_ADDR']

        # Allow 10 writes per minute on average for one authenticated user
        rateWriteMax = 10
        try:
            self.ua = SGetSigned('ua', req.COOKIES['userAuth'])
        except:
            # Only 2 writes per minute for anonymous user
            self.ua = self.ip
            rateWriteMax = 2

        if Block.FBlocked(self.ua):
            return
        self.mpAllowed.add('view')
        self.user = users.get_current_user()
        if users.is_current_user_admin():
            self.mpAllowed.add('admin')
        rate = MemRate("throttle.ua.%s" % self.ua, rateWriteMax, 60)
        if not rate.Exceeded():
            self.mpAllowed |= set(['view-count', 'share', 'comment'])
        
    def FAllow(self, perm):
        return self.perm[perm]
    
    def Require(self, perm):
        if not self.FAllow(perm):
            message = "Authorization Error"
            code = "Fail/Auth"
            if perm in self.mpPermMessage:
                message = self.mpPermMessage[perm]
            if perm in self.mpPermCode:
                code = self.mpPermCode[perm]
            raise Error(message, code)
        
    def FRepeated(self):
        # Check for successive duplicate requests - same user, same path
        key = 'repeat.ua.%s' % self.ua
        repeat = memcache.get(key)
        if repeat == self.req.get_full_path():
            return True
        memcache.set(key, self.req.get_full_path())
        return False

class Block(db.Model):
    # Block requests for abuse by IP or User Auth cookie
    ua = db.StringProperty(required=True)
    dateCreated = db.DateTimeProperty()
    
    @staticmethod
    def Create(ua):
        if Block.FBlocked(ua):
            return
        dateCreated = local.dtNow
        block = Block.get_or_insert(key_name=ua, ua=ua, dateCreated=dateCreated)
        block.put()
        memcache.set(self.KeyFromUa(ua), True)
        
    @staticmethod
    def FBlocked(ua):
        key = Block.KeyFromUa(ua)
        block = memcache.get(key)
        if block is not None:
            return True
        block = Block.get_by_key_name(key)
        if block is not None:
            memcache.set(key, True)
            return True
        return False
    
    @staticmethod
    def KeyFromUa(ua):
        return 'block.ua.%s' % ua
    

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

    http_status = 200
    if obj['status'] == 'Fail/NotFound':
        http_status = 404  
    t = loader.get_template('error.html')
    logging.info("Error: %r" % obj)
    AddToResponse(obj)
    resp = HttpResponse(t.render(Context(FinalResponse())))
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
    raise Error("The %s page, %s/%s, does not exist" % (settings.sSiteName, local.stHost, id), obj={'id':id, 'status':'Fail/NotFound'})

def IsJSON():
    return local.req.has_key("callback")

def HttpJSON(req, obj=None):
    if obj is None:
        obj = {}
    if not 'status' in obj:
        obj['status'] = 'OK'
    resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=JavaScriptEncoder)), mimetype="application/x-javascript")
    return resp

def AddToResponse(mp):
    local.mpResponse.update(mp)

def FinalResponse():
    AddToResponse({
        'elapsed': ResponseTime(),
        'now': local.dtNow,
        'username': local.cookies['username'],
        'analytics_code': settings.sAnalyticsCode,
        'site_name': settings.sSiteName,
        'site_host': settings.sSiteHost,
        'host': local.stHost,
        })
    return local.mpResponse
    
class ResponseTime(object):
    # Object looks like a string object - evaluates with time since start of request
    def __str__(self):
        ddt = datetime.now() - local.dtNow 
        sec = ddt.seconds + float(ddt.microseconds)/1000000
        return "%1.2f" % sec
        
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

def RequireUserAuth(hard=False):
    # Tries to confirm signed authentication token
    # If missing, will allow a limited number of authentications per unique IP
    # Returns raw IP address for anonymous users as unique user key
    # Returns IP~DateIssued~Rand for truly authenticated users
    try:
        s = SGetSigned('ua', local.cookies['userAuth'])
        return s
    except:
        if hard:
            raise Error("Failed Authentication", "Fail/Auth")
    rate = MemRate("anon.%s" % local.ipAddress, 10, 60)
    rate.Limit()
    return local.ipAddress

def SUserAuth():
    import random
    return "~".join((local.ipAddress, local.dtNow.strftime('%m/%d/%Y %H:%M'), str(random.randint(0, 10000))))
    
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

def SGetSigned(type, s, sError="Failed Authentication"):
    # Raise exception if s is not a valid signed string of the correct type.  Returns
    # original (unsigned) string if succeeds.
    try:
        m = regSigned.match(s)
        if SSign(m.group(1), m.group(2)) == s:
            return m.group(2)
    except:
        pass
    logging.warning("Signed failure: %s: %s" % (type, s))
    raise Error(sError, 'Fail/Auth')

# --------------------------------------------------------------------
# Per-request global variables stored in this thread-local global
# --------------------------------------------------------------------
local = threading.local()
