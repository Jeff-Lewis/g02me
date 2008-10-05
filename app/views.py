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
    url = req.GET["url"]
    map = Map.FindUrl(url)
    if map == None:
        if req.has_key("title"):
            title = req.GET["title"] or ""
        else:
            title = url
        id = Globals.IdNext()
        map = Map(key_name="K:%s" % id, url=url, title=unicode(title, 'utf8'))
    map.Shared();
    if req.has_key("callback"):
        obj = {'status':'OK', 'url':url, 'id':map.GetId(), 'viewed':map.viewCount, 'shared':map.shareCount,
               'created':map.dateCreated}
        resp = HttpResponse("%s(%s);" % (req.GET["callback"], simplejson.dumps(obj, cls=util.JavaScriptEncoder)))
        # TODO: Set mime type
        return resp
    return HttpResponseRedirect("/%s" % map.GetId())

def MakeComment(req):
    id = req.GET.get('id', '').strip()
    comment = req.GET.get('comment', '').strip()
    
    map = Map.Lookup(id)
    reg = re.compile(r"^( *([a-zA-Z0-9_\.\-+]+) *: *)?([^\[]*) *(\[(.*)\])? *$")
    m = reg.match(comment)
    logging.info("c: %s m: %s map: %s" % (comment, m, map))
    if m == None or map == None:
        return render_to_response('error.html', {'strError' : "The G02.ME page, <i>http://g02.me/%s</i>, does not exist" % id})
    username = m.group(2)
    comment = m.group(3)
    tags = m.group(5)
    logging.info("u: %s c: %s t: %s" % (username, comment, tags))
    map.AddComment(username=username, comment=comment, tags=tags)
    return HttpResponseRedirect("/info/%s" % map.GetId())

def Head(req, id):
    InitReq(req)
    map = Map.Lookup(id)
    if map == None:
        return render_to_response('error.html', {'strError' : "The G02.ME page, <i>http://g02.me/%s</i>, does not exist" % id})
    map.Viewed()
    comments = map.comment_set.fetch(100)
    return render_to_response('head.html', {'map': map, 'comments':comments})

def FrameSet(req, id):
    InitReq(req)
    map = Map.Lookup(id)
    if map == None:
        return render_to_response('error.html', {'strError' : "The G02.ME page, <i>http://g02.me/%s</i>, does not exist" % id})
    return render_to_response('mapped.html', {'map':map})

def UserHistory(req, username):
    InitReq(req)
    return render_to_response('error.html', {'strError' : "User view yet implemented: %s" % username})

def TagHistory(req, tagname):
    InitReq(req)
    return render_to_response('error.html', {'strError' : "Tag view yet implemented: %s" % tagname})

def InitReq(req):
    # Store the http request for URI generation, in a thread local
    # TODO: Put in MiddleWare?
    util.local.stHost = "http://" + req.META["HTTP_HOST"] + "/"
