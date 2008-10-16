from google.appengine.ext import db
from google.appengine.api import users
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
from util import *
from models import *

import logging
import simplejson
from sys import exc_info

def Home(req):
    InitReq(req)
    return render_to_response('home.html', {'host':local.stHost, 'pages':Map.TopPages()})

def MakeAlias(req):
    try:
        map = Map.FindOrCreateUrl(req.GET.get('url', ""), req.GET.get('title', ""))
        if req.has_key("callback"):
            return HttpJSON(req, obj=map.JSON())
        return HttpResponseRedirect("/%s" % map.GetId())
    except Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def MakeComment(req):
    try:
        id = req.GET.get('id', "").strip()
        
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
            
        parts = Comment.Parse(req.GET.get('comment', ""))

        map.AddComment(username=parts['username'], comment=parts['comment'], tags=parts['tags'])
        if req.has_key("callback"):
            return HttpJSON(req, obj=map.JSON())
        return HttpResponseRedirect("/info/%s" % map.GetId())
    except Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def Head(req, id):
    # http://g02me/info/N
    try:
        InitReq(req)
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
        map.Viewed()
        if req.has_key("callback"):
            return HttpJSON(req, obj=map.JSON())
        return render_to_response('head.html', {'map': map})
    except Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def FrameSet(req, id):
    # http://g02me/N
    try:
        InitReq(req)
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
        if req.has_key("callback"):
            map.Viewed()
            return HttpJSON(req, obj=map.JSON())
        return render_to_response('mapped.html', {'map':map})
    except Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def UserHistory(req, username):
    InitReq(req)
    return HttpError(req, "User view not yet implemented: %s" % username)

def TagHistory(req, tagname):
    InitReq(req)
    return HttpError(req, "Tag view not yet implemented: %s" % tagname)

def Admin(req):
    try:
        user = RequireAdmin(req)
        return render_to_response('admin.html',
              {'user':user,
               'req':req,
               'logout':users.create_logout_url(req.get_full_path()),
               'Broken':Map.ss.Broken(),
               })
    except DirectResponse, dr:
        logging.info("Caught direct response")
        return dr.resp
    except Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

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
    
def InitReq(req):
    # Store the http request for URI generation, in a thread local
    # TODO: Put in MiddleWare?
    local.stHost = "http://" + req.META["HTTP_HOST"] + "/"

def RaiseNotFound(id):
    raise Error("The G02.ME page, http://g02.me/%s, does not exist" % id, obj={'id':id, 'status':'Fail/NotFound'})

def HttpError(req, stError, obj={}):
    if req.has_key("callback"):
        if not 'status' in obj:
            obj['status'] = 'Fail'
        obj['message'] = stError
        logging.info('JSON Error: %(message)s (%(status)s)' % obj)
        return HttpJSON(req, obj=obj)
    logging.info('UI Error: %s' % stError)
    return render_to_response('error.html', {'strError' : stError})

def HttpJSON(req, obj={}):
    if not 'status' in obj:
        obj['status'] = 'OK'
    resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=JavaScriptEncoder)))
    # TODO: Set mime type
    return resp
