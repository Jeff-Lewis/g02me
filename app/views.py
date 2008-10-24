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

def CatchAll(req):
    raise Error("Page not found", "Fail/NotFound")

def MakeAlias(req):
    map = Map.FindOrCreateUrl(req.GET.get('url', ""), req.GET.get('title', ""))
    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/%s" % map.GetId())

def Lookup(req):
    map = Map.FindUrl(req.GET.get('url', ""))
    if map is None:
        raise Error("No shortened url exists", "Fail/NotFound")
    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    logging.info("lookup")
    return HttpResponseRedirect("/%s" % map.GetId())

def DoComment(req, command=None):
    if command == 'delete':
        cid = req.GET.get('cid', '').strip()
        try:
            cid = int(cid)
        except:
            raise Error("Invalid comment id: %s" % cid)
        comment = Comment.get_by_id(int(cid))
        if comment is None:
            raise Error("Comment id=%d does not exists" % cid, 'Fail/NotFound')
        map = comment.map
        comment.Delete()
        
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
    return render_to_response('head.html', {'map': map, 'username':local.username, 'TopTags':map.TopTags()})

def FrameSet(req, id):
    # http://g02me/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    if IsJSON():
        map.Viewed()
        return HttpJSON(req, obj=map.JSON())
    return render_to_response('mapped.html', {'map':map})

def UserView(req, username):
    if IsJSON():
        return HttpJSON(req, obj=Comment.ForUserJSON(username))
    comments = Comment.ForUser(username)
    return render_to_response('user.html', {'username':username, 'comments':comments})

def TagView(req, tag):
    if IsJSON():
        return HttpJSON(req, Map.TopJSON(tag=tag))
    return render_to_response('tag.html', {'tag':tag, 'host':local.stHost, 'pages':Map.TopPages(tag=tag)})

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
                
        if command == 'clean-broken-comments':
            comments = Comment.Broken()
            logging.info("Removing %d broken comments" % len(comments))
            for comment in comments:
                comment.delete()
                
        if command == 'fix-tag-counts':
            maps = Map.FindBadTagCounts()
            logging.info("Fixing %d bad tag counts" % len(maps))
            Map.FixTagCounts(maps)

        return HttpResponseRedirect("/admin/")

    return render_to_response('admin.html',
          {'user':user,
           'req':req,
           'logout':users.create_logout_url(req.get_full_path()),
           'Broken':Map.ss.Broken(),
           'BadComments':Comment.BadComments(),
           'BrokenComments':Comment.Broken(),
           'BadCounts':Map.FindBadTagCounts(),
           })
