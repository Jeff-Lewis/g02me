from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
import util

import logging
from sys import exc_info

class Map(db.Model):
    url = db.StringProperty(required=True, validator=util.NormalizeUrl)
    title = db.StringProperty(validator=util.TrimString)
    dateCreated = db.DateProperty(auto_now=True)
    viewCount = db.IntegerProperty(default=0)
    shareCount = db.IntegerProperty(default=0)
    
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
        return {'host':util.local.stHost,
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

class Comment(db.Model):
    username = db.StringProperty()
    