from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache

import logging
from sys import exc_info

class Map(db.Model):
    id = db.IntegerProperty()
    url = db.StringProperty()
    title = db.StringProperty()
    dateCreated = db.DateProperty()
    
    @classmethod
    def Lookup(cls, id):
        # just use id as key - more frequent than url lookup
        query = db.Query(Map)
        query.filter('id =', int(id))
        map = query.get()
        return map
    
    @classmethod
    def FindUrl(cls, url):
        query = db.Query(Map)
        query.filter('url =', url)
        map = query.get()
        return map

# TODO: Use a sharded counter - see Google IO video     
class Globals(db.Model):
    idNext = db.IntegerProperty(default=1)
    
    @classmethod
    def IdNext(cls):
        glob = cls.get_or_insert("current")
        id = glob.idNext
        glob.idNext = glob.idNext + 1
        glob.put()
        return id

def MakeAlias(req):
    url = req.GET["url"]
    map = Map.FindUrl(url)
    if map == None:
        if req.has_key("title"):
            title = req.GET["title"]
        id = Globals.IdNext()
        map = Map(id=id, url=url, title=title)
        map.put()
    return HttpResponseRedirect("/%s" % str(map.id))

def Head(req):
    id = req.GET["id"]
    map = Map.Lookup(int(id))
    if map == None:
        return render_to_response('error.html', {'strError' : "No such id: %s" % id})
    return render_to_response('head.html', {'id':map.id, 'url':map.url, 'title':map.title})

def FrameSet(req, id):
    logging.info(id)
    map = Map.Lookup(int(id))
    if map == None:
        return render_to_response('error.html', {'strError' : "No such id: %s" % id})
    return render_to_response('mapped.html', {'id':map.id, 'url':map.url, 'title':map.title})

    
    