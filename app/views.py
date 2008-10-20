from google.appengine.ext import db
from google.appengine.api import users
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect

from util import *
from models import *

import logging

def Home(req):
    if IsJSON():
        return HttpJSON(req, Map.TopJSON())
    return render_to_response('home.html', {'host':local.stHost, 'pages':Map.TopPages()})

def MakeAlias(req):
    map = Map.FindOrCreateUrl(req.GET.get('url', ""), req.GET.get('title', ""))
    if req.has_key("callback"):
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/%s" % map.GetId())

def DoComment(req, command=None):
    if command == 'delete':
        cid = req.GET.get('cid', '').strip()
        comment = Comment.get_by_id(int(cid))
        map = comment.map
        comment.delete();
        
    if command is None:
        id = req.GET.get('id', "").strip()
        
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
            
        parts = Comment.Parse(req.GET.get('comment', ""))
    
        try:
            map.AddComment(username=parts['username'], comment=parts['comment'], tags=parts['tags'])
        except:
            pass

    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/info/%s" % map.GetId())
    

def Head(req, id):
    # http://g02me/info/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    map.Viewed()
    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    t = loader.get_template('head.html')
    resp = HttpResponse(t.render(Context({'map': map, 'username':local.username})))
    resp['Expires'] = '0'
    return resp

def FrameSet(req, id):
    # http://g02me/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    if IsJSON():
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
        if command == 'clean-broken':
            scores = Map.ss.Broken()
            logging.info("Removing %d broken scores" % len(scores))
            for score in scores:
                score.delete()
                
        if command == 'clean-comments':
            comments = Comment.BadComments()
            logging.info("Removing %d empty comments" % len(comments))
            for comment in comments:
                comment.delete()

        return HttpResponseRedirect("/admin/")

    return render_to_response('admin.html',
          {'user':user,
           'req':req,
           'logout':users.create_logout_url(req.get_full_path()),
           'Broken':Map.ss.Broken(),
           'BadComments':Comment.BadComments(),
           })
