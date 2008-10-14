from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
import re
import util
from models import *

import logging
import simplejson
from sys import exc_info

def Home(req):
    InitReq(req)
    return render_to_response('home.html', {'host':util.local.stHost, 'pages':Map.TopPages()})

def MakeAlias(req):
    try:
        url = req.GET["url"]
        map = Map.FindUrl(url)
        if map == None:
            title = ""
            if req.has_key("title"):
                title = req.GET["title"] or ""
            id = Globals.IdNext()
            map = Map(key_name="K:%s" % id, url=url, title=title)
        map.Shared()
        if req.has_key("callback"):
            return HttpJSON(req, obj=map.JSON())
        return HttpResponseRedirect("/%s" % map.GetId())
    except util.Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def MakeComment(req):
    try:
        id = req.GET.get('id', '').strip()
        comment = req.GET.get('comment', '').strip()
        
        map = Map.Lookup(id)
        reg = re.compile(r"^( *([a-zA-Z0-9_\.\-+]+) *: *)?([^\[]*) *(\[(.*)\])? *$")
        m = reg.match(comment)
    
        if m == None:
            raise Error("Could not parse comment", obj={'id':id})
    
        if map == None:
            RaiseNotFound(id)
    
        username = m.group(2)
        comment = m.group(3)
        tags = m.group(5)
        map.AddComment(username=username, comment=comment, tags=tags)
        if req.has_key("callback"):
            return HttpJSON(req, obj=map.JSON())
        return HttpResponseRedirect("/info/%s" % map.GetId())
    except util.Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def Head(req, id):
    try:
        InitReq(req)
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
        map.Viewed()
        if req.has_key("callback"):
            return HttpJSON(req, obj=map.JSON())
        return render_to_response('head.html', {'map': map})
    except util.Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def FrameSet(req, id):
    try:
        InitReq(req)
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
        if req.has_key("callback"):
            map.Viewed()
            return HttpJSON(req, obj=map.JSON())
        return render_to_response('mapped.html', {'map':map})
    except util.Error, e:
        return HttpError(req, e.obj['message'], obj=e.obj)

def UserHistory(req, username):
    InitReq(req)
    return HttpError(req, "User view not yet implemented: %s" % username)

def TagHistory(req, tagname):
    InitReq(req)
    return HttpError(req, "Tag view not yet implemented: %s" % tagname)

def InitReq(req):
    # Store the http request for URI generation, in a thread local
    # TODO: Put in MiddleWare?
    util.local.stHost = "http://" + req.META["HTTP_HOST"] + "/"

def RaiseNotFound(id):
    raise util.Error("The G02.ME page, http://g02.me/%s, does not exist" % id, obj={'id':id, 'status':'Fail/NotFound'})

def HttpError(req, stError, obj={}):
    if req.has_key("callback"):
        if not 'status' in obj:
            obj['status'] = 'Fail'
        obj['message'] = stError
        return HttpJSON(req, obj=obj)
    return render_to_response('error.html', {'strError' : stError})

def HttpJSON(req, obj={}):
    if not 'status' in obj:
        obj['status'] = 'OK'
    resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=util.JavaScriptEncoder)))
    # TODO: Set mime type
    return resp
