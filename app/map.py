from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse
from google.appengine.api import memcache

import logging
from sys import exc_info

class Map(db.Model):
    id = db.IntegerProperty()
    url = db.StringProperty()
    title = db.StringProperty()
    dateCreated = db.DateProperty()
    
class Globals(db.Model):
    idNext = db.IntegerProperty(default=1)
    
    @classmethod
    def IdNext(cls):
        glob = cls.get_or_insert("current")
        id = glob.idNext
        glob.idNext = glob.idNext + 1
        glob.put()
        return id

def Lookup(req):
    url = req.GET["url"]
    if req.has_key("title"):
        title = req.GET["title"]
    id = Globals.IdNext()
    map = Map(id=id, url=url, title=title)
    map.put()
    return render_to_response('mapped.html', locals())
    
    