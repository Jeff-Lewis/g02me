from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
import util
from models import *

import logging
from sys import exc_info

def Home(req):
    InitReq(req)
    return render_to_response('home.html', {'host':util.local.stHost})

def MakeAlias(req):
    url = req.GET["url"]
    map = Map.FindUrl(url)
    if map == None:
        if req.has_key("title"):
            title = req.GET["title"] or ""
        id = Globals.IdNext()
        map = Map(key_name="K:%s"%id, url=url, title=unicode(title, 'utf8'))
    map.shareCount = map.shareCount + 1
    map.put()
    return HttpResponseRedirect("/%s" % map.GetId())

def Head(req):
    InitReq(req)
    id = req.GET["id"]
    map = Map.Lookup(id)
    if map == None:
        return render_to_response('error.html', {'strError' : "The G02.ME page, <i>http://g02.me/%s</i>, does not exist" % id})
    map.viewCount = map.viewCount + 1
    map.put()
    return render_to_response('head.html', {'map': map})

def FrameSet(req, id):
    InitReq(req)
    map = Map.Lookup(id)
    if map == None:
        return render_to_response('error.html', {'strError' : "The G02.ME page, <i>http://g02.me/%s</i>, does not exist" % id})
    return render_to_response('mapped.html', {'map':map})

def InitReq(req):
    # Store the http request for URI generation, in a thread local
    # TODO: Put in MiddleWare?
    util.local.stHost = "http://" + req.META["HTTP_HOST"] + "/"
