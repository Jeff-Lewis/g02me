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
    
    def process_request(self, req):
        import models

        host = req.META["HTTP_HOST"]

        # Redirect to the primary hosted domain
        if settings.ENVIRONMENT == "hosted" and host in settings.mpSiteAlternates:
            return HttpResponsePermanentRedirect('http://%s%s' % (settings.sSiteHost, req.path))
        
        # Initialize thread-local variables for this request
        local.req = req
        local.stHost = "http://" + host + "/"
        local.ipAddress = req.META['REMOTE_ADDR']
        
        # A place to copy any cookies we want during request processing
        local.cookies = {}
        
        # A place to put dictionary values for template responses
        local.mpResponse = {}
        
        local.dtNow = datetime.now()
        local.sSecret = models.Globals.SGet(settings.sSecretName, "test server key")
        
        requser = ReqUser(req)
        
        if requser.fAnon:
            requser.SetMaxRate('write', 1)
            requser.Allow('share')
        else:
            requser.SetMaxRate('write', 10)
            requser.Allow('share', 'score', 'view-count', 'comment')
            
        if req.method == 'GET':
            local.mpParams = req.GET
        else:
            local.mpParams = req.POST

        local.fJSON = local.mpParams.has_key("callback")

        # API calls allowed if csrf field is validated to the current user OR
        # if a signed apikey is given
        try:
            if local.mpParams['csrf'] == requser.uid:
                requser.Allow('api', 'post')
        except: pass
        
        try:
            sAPI = SGetSigned('api', local.mpParams['apikey'])
            # Format: user~yyyy-mm-dd (expiration date)
            rgAPI = sAPI.split('~')
            dtExpires = datetime.strptime(rgAPI[1], '%Y-%m-%d')
            if dtExpires > local.dtNow:
                requser.Allow('api')
                requser.SetMaxRate('write', 60)
        except: pass   
        
        local.requser = requser
        
    def process_response(self, req, resp):
        # If the user has no valid userAuth token, given them one for the next request
        local.cookies.update(local.requser.UserCookies())

        for name in local.cookies:
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
        
def IsJSON():
    # BUG: Remove
    return local.fJSON;
        
# --------------------------------------------------------------------
# User information for the request.
# - Authentication
# - Permissions
# - Request throttling
# - API request permission
# - Admin access
# - Virtual session state (cookie based)
# --------------------------------------------------------------------

class ReqUser(object):
    mpPermMessage = {}
    mpPermCode = {}

    def __init__(self, req):
        self.req = req
        self.fAnon = True
        self.mpRates = {}
        self.username = ''
        
        # Nothing allowed by default!
        self.mpPermit = set()

        if Block.Blocked(local.ipAddress):
            return

        try:
            self.uidSigned = req.COOKIES['userAuth']
            self.uid = SGetSigned('uid', self.uidSigned)
            if Block.Blocked(self.uid):
                return;
            self.fAnon = False
        except:
            self.uid = self.SGenUID()
            self.uidSigned = SSign('uid', self.uid)
            logging.info("Anon-new: %s" % self.uid)

        self.Allow('read')
        
        self.username = req.COOKIES.get('username', '')
        
        self.user = users.get_current_user()
        if users.is_current_user_admin():
            self.Allow('admin')
        
    def SetMaxRate(self, sName, rate):
        # Set the maximum request rate (per minute) for a given activity
        self.Allow(sName)
        self.mpRates[sName] = MemRate('user.%s' % sName, rate, 60)
        
    def FRateExceeded(self, sName, value=1):
        if sName not in self.mpRates:
            return False
        return self.mpRates[sName].FExceeded(value=value)
    
    def SetVar(self, name, value, priority=1):
        # Save a session variable for the user - only replace current value if the same or higher
        # priority
        if name not in self.mpVars or priority >= self.mpVarPri[name]:
            self.mpVars[name] = value
            self.mpVarPri[name] = priority
        return self.mpVars[name]
    
    def GetVar(self, name, default=None):
        if name not in self.mpVars:
            return default
        return self.mpVars[name]
            
    def Allow(self, *args):
        for sPerm in args:
            self.mpPermit.add(sPerm)
    
    def FAllow(self, *args):
        for sPerm in args:
            if sPerm not in self.mpPermit or self.FRateExceeded(sPerm):
                return False
        return True
    
    def Require(self, *args):
        for sPerm in args:
            if not self.FAllow(sPerm):
                message = self.mpPermMessage.get(sPerm, "Authorization Error (%s)" % sPerm)
                code = self.mpPermCode.get(sPerm, "Fail/Auth/%s" % sPerm)
                raise Error(message, code)
            
    def FOnce(self, key):
        if memcache.get('user.once.%s.%s' % (self.UserId(), key)):
            return False
        memcache.set('user.once.%s.%s' % (self.UserId(), key), True)
        return True

    def UserId(self):
        if self.fAnon:
            return local.ipAddress
        return self.uid
    
    @staticmethod
    def SGenUID():
        # Generate a unique user ID: IP~Date~Random
        import random
        return "~".join((local.ipAddress, local.dtNow.strftime('%m/%d/%Y %H:%M'), str(random.randint(0, 10000))))
    
    def UserCookies(self):
        return {'userAuth': self.uidSigned,
                'username': self.username,
                }

class Block(db.Model):
    # Block requests for abuse by IP or User Auth key
    dateCreated = db.DateTimeProperty()
    secsMem = 3*60
    
    @staticmethod
    def Create(sKey):
        block = Block.Blocked(sKey)
        if block:
            return block
        sMemKey = Block.MemKey(sKey)
        block = Block.get_or_insert(key_name=sMemKey, dateCreated=local.dtNow)
        block.put()
        memcache.set(sMemKey, self, Block.secsMem)
        return block
        
    @staticmethod
    def Blocked(sKey):
        sMemKey = Block.MemKey(sKey)
        block = memcache.get(sMemKey)
        if block is not None:
            return block
        block = Block.get_by_key_name(sMemKey)
        if block is not None:
            memcache.set(sMemKey, block, Block.secsMem)
            return block
        return None
    
    @staticmethod
    def MemKey(sKey):
        return 'block.%s' % sKey
    

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
    AddToResponse({'status_major': obj['status'].split('/')[0]})
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

def HttpJSON(req, obj=None):
    if obj is None:
        obj = {}
    if not 'status' in obj:
        obj['status'] = 'OK'
    obj['secsResponse'] = str(ResponseTime())
    resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=JavaScriptEncoder, indent=4)), mimetype="application/x-javascript")
    return resp

def AddToResponse(mp):
    local.mpResponse.update(mp)
    
def FinalResponse():
    AddToResponse({
        # Elapsed time evaluates when USED
        'elapsed': ResponseTime(),
        'now': local.dtNow,
        'req': local.req,

        'username': local.requser.username,
        'userauth': local.requser.uidSigned,
        'csrf': local.requser.uid,
        'user': local.requser.user,
        'fAnon': local.requser.fAnon,

        'site_name': settings.sSiteName,
        'site_host': settings.sSiteHost,
        'host': local.stHost,

        'analytics_code': settings.sAnalyticsCode,        
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

# TODO: These should go away - replaced by ReqUser functions
        
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
    if not local.requser.fAnon:
        return local.requser.uid
    if hard:
        raise Error("Failed Authentication", "Fail/Auth")
    rate = MemRate("anon.%s" % local.ipAddress, 10, 60)
    rate.Limit()
    return local.ipAddress

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

def SSign(type, s, sSecret=None):
    # Sign the string using the server secret key
    # type is a short string that is used to distinguish one type of signed content vs. another
    # (e.g. user auth from).
    if sSecret is None:
        sSecret = local.sSecret
    hash = sha1('~'.join((type, str(s), sSecret))).hexdigest().upper()
    return '~'.join((type, str(s), hash))

regSigned = re.compile(r"^(\w+)~(.*)~[0-9A-F]{40}$")

def SGetSigned(type, s, sSecret=None, sError="Failed Authentication"):
    # Raise exception if s is not a valid signed string of the correct type.  Returns
    # original (unsigned) string if succeeds.
    try:
        m = regSigned.match(s)
        if SSign(type, m.group(2), sSecret) == s:
            return m.group(2)
    except:
        pass
    if s != '':
        logging.warning("Signed failure: %s: %s" % (type, s))
    raise Error(sError, 'Fail/Auth')

# --------------------------------------------------------------------
# Per-request global variables stored in this thread-local global
# --------------------------------------------------------------------
local = threading.local()
