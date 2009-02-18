from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import db

from django.http import HttpResponse, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import render_to_response
from django.template import loader, Context, Template

import settings
from timescore.models import Rate

import threading
from urlparse import urlsplit, urlunsplit
import logging
import simplejson
from hashlib import sha1
import re
import sys
import traceback

# Some letters and numbers have been removed to ensure that humans can read the identifies
# without ambiguity.
sIDChars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
nIDChars = len(sIDChars)

def IntToSID(i):
    # Convert int to "base 64" string - not compatible with Base64 string standard
    s = ''
    while i != 0:
        b = i % nIDChars
        s = sIDChars[b] + s
        i = i/nIDChars
    return s

# All all the country domains (2 letter), and the currently defined gTLD's
# BUG - handle Unicode domains
regDomain = re.compile(r"^([a-z0-9][a-z0-9-]*\.)+([a-z]{2}|" + \
    r"aero|asia|biz|cat|com|coop|edu|gov|info|int|jobs|mil|mobi|museum|net|org|pro|tel|travel)$")

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
    if rgURL[1]:
        rgURL[1] = rgURL[1].lower()
    if not rgURL[1] or not regDomain.search(rgURL[1]) or len(rgURL[1]) > 255:
        raise Error("Invalid URL: %s" % urlunsplit(rgURL))
    
    # Always end naked domains with a trailing slash as canonical
    if rgURL[2] == '':
        rgURL[2] = '/';
    return urlunsplit(rgURL)

def Href(url):
    # Quote url text so it can be embedded in an HTML href
    ich = url.find('//')
    path = url[ich+2:].replace('"', '%22')
    return url[0:ich+2] + path

def TrimString(st):
    if st == None:
        st = ''
    return re.sub('[\000-\037]', '', str(st)).strip()

def Slugify(s):
    "Converts to lowercase, removes non-alpha chars and converts spaces to hyphens"
    s = re.sub('[^\w\s-]', '', s).strip().lower()
    s = re.sub('[-\s]+', '-', s)
    s = re.sub('(^-+)|(-+$)', '', s)
    return s

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
        from go2me import models

        local.ipAddress = req.META['REMOTE_ADDR']
        local.dtNow = datetime.now()
        host = req.META["HTTP_HOST"]
        local.sSecret = models.Globals.SGet(settings.sSecretName, "test server key")
        local.cookies = {}
        local.mpResponse = {}

        # Initialize thread-local variables for this request
        local.req = req
        local.stHost = "http://" + host + "/"

        # Enforce canonical URL's (w/o www) - only GET's are support here
        if settings.ENVIRONMENT == "hosted":
            if host in settings.mpSiteAlternates:
                return HttpResponsePermanentRedirect('http://%s%s' % (settings.sSiteHost, req.get_full_path()))
            # Redirect the old named blog to the new one
            if host == 'blog.g02.me':
                return HttpResponsePermanentRedirect('http://blog.go2.me%s' % req.get_full_path())

        local.requser = requser = ReqUser(req)
        
        """
        Add additional permissions to ReqUser object:

        'write': Can write to database (rate-limited)
        'share': Can share a link
        'score': Can update the score of a link
        'view-count': Can update the view count of a link
        'comment': Can add or delete a comment
        'api': Can make a data-modification request via JSON or POST api
        
        Note that multiple permission can be required to perform operations like 'comment'.
        """
        
        requser.SetMaxRate('write', local.ipAddress, 1)
        if requser.fAnon:
            requser.Allow('share')
        else:
            requser.Allow('share', 'score', 'view-count', 'comment')
            requser.SetMaxRate('write', requser.uid, 10)
            
        if req.method == 'GET':
            local.mpParams = req.GET
        else:
            local.mpParams = req.POST

        local.fJSON = local.mpParams.has_key("callback")

        # API calls allowed if csrf field is validated to the current user OR
        # if a signed apikey is given
        try:
            if local.mpParams['csrf'] == requser.uid:
                requser.SetMaxRate('write', requser.uid, 10)
                requser.Allow('api', 'post')
        except: pass
        
        # Static apikey: dev~rate~yyyy-mm-dd (expiration date)
        try:
            sAPI = SGetSigned('api', local.mpParams['apikey'])
            
            rgAPI = sAPI.split('~')
            dev = str(rgAPI[0])
            rate = int(rgAPI[1])
            dtExpires = datetime.strptime(rgAPI[2], '%Y-%m-%d')
            if dtExpires > local.dtNow:
                requser.SetMaxRate('write', dev, rate)
                requser.Allow('api')
        except: pass
        
        # Client apikey: ip~rate
        try:
            sAPI = SGetSigned('apiIP', local.mpParams['apikey'])

            rgAPI = sAPI.split('~')
            ip = str(rgAPI[0])
            rate = int(rgAPI[1])
            if local.ipAddress == ip:
                requser.SetMaxRate('write', ip, rate)
                requser.Allow('api')
        except: pass        
        
        # Redirect from home to the profile page if the user profile is not complete
        if not local.fJSON and requser.profile and not requser.profile.IsValid() and req.path == '/':
             return HttpResponseRedirect("/profile/")  
        
    def process_response(self, req, resp):
        # If the user has no valid userAuth token, given them one for the next request
        try:
            local.cookies.update(local.requser.UserCookies())
        except: pass

        for name in local.cookies:
            if local.cookies[name]:
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
        sBacktrace = ''.join(traceback.format_list(traceback.extract_tb(sys.exc_info()[2])))
        
        if isinstance(e, Error):
            logging.info("Exception: %r" % e)
            logging.info(sBacktrace)
            return HttpError(req, e.obj['message'], obj=e.obj)
        
        logging.error("Unknown exception: %r" % e)
        logging.error(sBacktrace)
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
    """
    Manage permissions for the user who is making this request.
    Looks for (and sets) cookies: userAuth and username
    
    Built in permissions: 'read', 'admin', 'user'
    """

    def __init__(self, req):
        from go2me.profile import Profile        

        self.req = req
        self.fAnon = True
        self.mpRates = {}
        self.username = ''
        self.usernameSigned = ''
        self.profile = None
        
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
        
        # If we have lost Google Auth - see if we have the longer lived
        # signin cookie instead.
        user = users.get_current_user()
        if user:
            self.profile = Profile.FindOrCreate(user, req.COOKIES.get('username', ''), self.UserId())
        else:
            try:
                sSignin = req.COOKIES['signin']
                self.username = SGetSigned('signin', sSignin)
                self.profile = Profile.Lookup(self.username)
                if self.profile:
                    self.usernameSigned = sSignin
            except: pass
        
        if not self.profile:    
            try:
                self.SetOpenUsername(req.COOKIES.get('username', ''), fForce=True)
            except: pass
            
        # Logout any banned usernames
        if self.profile and self.profile.fBanned:
            self.profile = None
            self.username = ''
            self.usernameSigned = ''

        if self.profile:
            # User must fill out a valid profile before using it
            self.Allow('user')
            self.username = self.profile.username
            if not self.usernameSigned:
                self.usernameSigned = SSign('signin', self.profile.username)
            if self.profile.fAdmin or users.is_current_user_admin():
                self.Allow('admin')
            
    def SetMaxRate(self, sName, sScope=None, rpm=None):
        # Set the maximum request rate (per minute) for a given activity
        # If mulitple calls are made, the last set rate applies.
        self.Allow(sName)
        self.mpRates[sName] = MemRate('%s.%s' % (sScope, sName), rpm)
        
    def RateExceeded(self, sPerm):
        # If a rate is exceeded, return the one that is exceeded
        if sPerm not in self.mpRates:
            return None
        rate = self.mpRates[sPerm]
        if rate.FExceeded():
            return rate
        return None

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
            
    def Disallow(self, *args):
        for sPerm in args:
            self.mpPermit.discard(sPerm)
    
    def Require(self, *args):
        if not self.FAllow(*args):
            if not local.fJSON:
                if self.sPermFail in ['user', 'admin']:
                    if self.profile is None or self.profile.fBanned:
                        raise DirectResponse(HttpResponseRedirect(users.create_login_url(local.req.get_full_path())))
                    raise DirectResponse(HttpResponseRedirect(users.create_logout_url(local.req.get_full_path())))               

            if self.sPermFail in ['user', 'admin']:
                raise Error(self.message, self.code, {'urlLogin': JSONLoginURL()})
            raise Error(self.message, self.code)
    
    def FAllow(self, *args):
        # Not thread safe - uses instance variables to store last error message
        for sPerm in args:
            if sPerm not in self.mpPermit:
                self.message = "Authorization Error (%s)" % sPerm
                self.code = "Fail/Auth/%s" % sPerm
                self.sPermFail = sPerm
                return False
                
            rate = self.RateExceeded(sPerm)
            if rate is not None:
                self.message = "Maximum request rate exceeded (%1.1f per minute - %d allowed for %s)" % \
                    (rate.RPM(), rate.rpmMax, rate.key)
                self.code = 'Fail/Busy/%s' % sPerm
                self.sPermFail = sPerm
                return False

        return True

        try:
            self.Require(*args)
            return True
        except:
            return False
            
    def FOnce(self, key):
        if memcache.get('user.once.%s.%s' % (self.UserId(), key)):
            return False
        memcache.set('user.once.%s.%s' % (self.UserId(), key), True, time=15*60)
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
                'signin': self.usernameSigned,
                }
        
    def SetOpenUsername(self, username, fSetEmpty=True, fForce=False):
        # Will only set username that is "available" (not used in an unbanned Profile, and will only allow
        # setting of names already used in comments if fForce is True)
        from go2me.models import Comment
        from go2me.profile import Profile
        if username == '':
            if not fSetEmpty:
                return;
            self.username = '';
            self.usernameSigned = ''
        
        if username == self.username:
            return
        
        profile = Profile.Lookup(username)
        if profile and not profile.fBanned:
            if IsJSON():
                raise Error("Username (%s) requires login" % username, 'Fail/Auth/user',
                    {'urlLogin': JSONLoginURL()})
            self.Require('user')

        if not fForce and Comment.FUsernameUsed(username):
            raise Error("Username (%s) already in use" % username, 'Fail/Auth/Used')

        self.username = username        

class MemRate(object):
    def __init__(self, key, rpmMax=None):
        self.rate = None
        self.key = key
        self.rpmMax = rpmMax
        self.fExceeded = None
        
    def FExceeded(self):
        if self.fExceeded is not None:
            return self.fExceeded

        self.EnsureRate()
        self.fExceeded = self.rate.FExceeded()
        memcache.set('rate.%s' % self.key, self.rate, 300)
        if self.fExceeded:
            logging.info('MemRate exceeded: %1.2f/%d for %s (%s)' % (self.rate.S*60, self.rpmMax, self.key, self.fExceeded))
        return self.fExceeded
    
    def RPM(self):
        # Return current number of requests per minute
        if self.rate is None:
            return 0.0
        return self.rate.S * 60.0
    
    def EnsureRate(self):
        if self.rate is None:
            self.rate = memcache.get('rate.%s' % self.key)
        if self.rate is None:
            self.rate = Rate(self.rpmMax, 60)

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

def HttpError(req, stError, obj=None):
    if obj is None:
        obj = {}
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
        
def JSONLoginURL():
    return users.create_login_url(local.mpParams.get('urlLogin', '/'))

def JSONLogoutURL():
    return users.create_logout_url(local.mpParams.get('urlLogin', '/'))
        
class DirectResponse(Exception):
    def __init__(self, resp):
        self.resp = resp
        
def RaiseNotFound(id):
    raise Error("The %s page, %s/%s, does not exist" % (settings.sSiteName, local.stHost, id), obj={'id':id, 'status':'Fail/NotFound'})

def HttpJSON(req, obj=None):
    if not IsJSON():
        raise Error("Missing ?callback= parameter for API call.")
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
        'profile': local.requser.profile,
        'is_anon': local.requser.fAnon,
        'is_admin': local.requser.FAllow('admin'),

        'site_name': settings.sSiteName,
        'site_host': settings.sSiteHost,
        'twitter_source': settings.sTwitterSource,
        'site_title': settings.sSiteTitle,
        'site_tagline': settings.sSiteTagline,
        'link_length': settings.nLinkLength,
        'host': local.stHost,

        'analytics_code': settings.sAnalyticsCode,
        'quantcast_acct': settings.sQuantcast,
        'ad_publisher_id': settings.sAdPublisherID,
        })
    return local.mpResponse
    
class ResponseTime(object):
    # Object looks like a string object - evaluates with time since start of request
    def __str__(self):
        ddt = datetime.now() - local.dtNow 
        sec = ddt.seconds + float(ddt.microseconds)/1000000
        return "%1.2f" % sec
        
def RunInTransaction(func):
    # Function decorator to wrap entire function in an App Engine transaction
    def _transaction(*args, **kwargs):
        return db.run_in_transaction(func, *args, **kwargs)
    return _transaction

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
