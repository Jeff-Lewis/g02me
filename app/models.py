from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
import util
from timescore.models import ScoreSet

import logging
from sys import exc_info

class Map(db.Model):
    ss = ScoreSet.GetSet("map")
    
    # Relative scores for user interactions
    scoreComment = 2
    scoreView = 1
    scoreShare = 3
    
    url = db.StringProperty(required=True, validator=util.NormalizeUrl)
    title = db.StringProperty(validator=util.TrimString)
    dateCreated = db.DateTimeProperty(auto_now=True)
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
        
    def AddComment(self, username, comment, tags):
        comm = Comment(map=self, username=username, comment=comment, tags=tags)
        comm.put()
        self.ss.Update(self, self.scoreComment)
        
    def CommentCount(self):
        # TODO: Inefficient for large comment streams - loads all in memory
        return self.comment_set.count();
    
    def Shared(self):
        self.shareCount = self.shareCount + 1
        self.put()
        self.ss.Update(self, self.scoreShare)
        
    def Viewed(self):
        self.viewCount = self.viewCount + 1
        self.put()
        self.ss.Update(self, self.scoreView)
        
# TODO: Use a sharded counter   
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
    username = db.StringProperty(validator=util.TrimString)
    comment = db.StringProperty(validator=util.TrimString)
    tags = db.StringProperty(validator=util.TrimString)
    map = db.ReferenceProperty(Map)
    dateCreated = db.DateTimeProperty(auto_now=True)
    
    def TagList(self):
        return self.tags.split(",")
    