from google.appengine.ext import db
from google.appengine.api import users
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
from util import *
from models import *

import logging
from sys import exc_info

def Home(req):
    return render_to_response('home.html', {'host':local.stHost, 'pages':Map.TopPages()})

def MakeAlias(req):
    map = Map.FindOrCreateUrl(req.GET.get('url', ""), req.GET.get('title', ""))
    if req.has_key("callback"):
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/%s" % map.GetId())

def MakeComment(req):
    id = req.GET.get('id', "").strip()
    
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
        
    parts = Comment.Parse(req.GET.get('comment', ""))

    map.AddComment(username=parts['username'], comment=parts['comment'], tags=parts['tags'])
    if req.has_key("callback"):
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/info/%s" % map.GetId())

def Head(req, id):
    # http://g02me/info/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    map.Viewed()
    if req.has_key("callback"):
        return HttpJSON(req, obj=map.JSON())
    return render_to_response('head.html', {'map': map})

def FrameSet(req, id):
    # http://g02me/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    if req.has_key("callback"):
        map.Viewed()
        return HttpJSON(req, obj=map.JSON())
    return render_to_response('mapped.html', {'map':map})

def UserHistory(req, username):
    raise Error("User view not yet implemented: %s" % username)

def TagHistory(req, tagname):
    raise Error("Tag view not yet implemented: %s" % tagname)

def Admin(req, command=None):
    user = RequireAdmin(req)
    
    if command:
        logging.info("admin command: %s" % command)
        if command == "clean-broken":
            scores = Map.ss.Broken()
            logging.info("Removing %d broken scores" % len(scores))
            for score in scores:
                score.delete()
        return HttpResponseRedirect("/admin")

    return render_to_response('admin.html',
          {'user':user,
           'req':req,
           'logout':users.create_logout_url(req.get_full_path()),
           'Broken':Map.ss.Broken(),
           })
