from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
import util

import logging
import threading
from sys import exc_info

class Map(db.Model):
    url = db.StringProperty(required=True, validator=util.NormalizeUrl)
    title = db.StringProperty(validator=util.TrimString)
    dateCreated = db.DateProperty(auto_now=True)
    
    @classmethod
    def KeyFromId(self, id):
        return "K:%s" % id

    @classmethod
    def Lookup(cls, id):
        # just use id as key - more frequent than url lookup
        map = Map.get_by_key_name(Map.KeyFromId(id))
        return map
    
    @classmethod
    def FindUrl(cls, url):
        url = util.NormalizeUrl(url)
        query = db.Query(Map)
        query.filter('url =', url)
        map = query.get()
        return map
    
    def GetId(self):
        return self.key().name()[2:]
    
    def GetDict(self):
        return {'host':local.stHost,
                'id':self.GetId(),
                'url':self.url,
                'title':self.title
                }

# TODO: Use a sharded counter - see Google I/O video     
class Globals(db.Model):
    idNext = db.IntegerProperty(default=1)
    
    @classmethod
    def IdNext(cls):
        glob = cls.get_or_insert("current")
        id = glob.idNext
        glob.idNext = glob.idNext + 1
        glob.put()
        return util.IntToS64(id)

def Home(req):
    InitReq(req)
    host = local.stHost
    return render_to_response('home.html', locals())

def MakeAlias(req):
    url = req.GET["url"]
    map = Map.FindUrl(url)
    if map == None:
        if req.has_key("title"):
            title = req.GET["title"] or ""
        id = Globals.IdNext()
        map = Map(key_name="K:%s"%id, url=url, title=unicode(title, 'utf8'))
        map.put()
    return HttpResponseRedirect("/%s" % map.GetId())

def Head(req):
    InitReq(req)
    id = req.GET["id"]
    map = Map.Lookup(int(id))
    if map == None:
        return render_to_response('error.html', {'strError' : "No such id: %s" % id})
    return render_to_response('head.html', map.GetDict())

def FrameSet(req, id):
    InitReq(req)
    logging.info(id)
    map = Map.Lookup(id)
    if map == None:
        return render_to_response('error.html', {'strError' : "No such id: %s" % id})
    return render_to_response('mapped.html', map.GetDict())

def InitReq(req):
    # Store the http request for URI generation, in a thread local
    local.stHost = "http://" + req.META["HTTP_HOST"] + "/"

local = threading.local()
    