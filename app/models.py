from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
import util
from timescore.models import ScoreSet

import logging
from sys import exc_info
from urlparse import urlsplit

class Map(db.Model):
    ss = ScoreSet.GetSet("map")
    
    # Relative scores for user interactions
    scoreComment = 2
    scoreView = 1
    scoreShare = 3
    
    # TODO: Add a database model for blacklisted domains
    blackList = {'g02.me':True, 'www.g02.me': True}
    
    url = db.StringProperty(required=True)
    title = db.StringProperty()
    dateCreated = db.DateTimeProperty(auto_now=True)
    viewCount = db.IntegerProperty(default=0)
    shareCount = db.IntegerProperty(default=0)
    
    def __init__(self, *args, **kw):
        db.Model.__init__(self, *args, **kw)
        
        # Validator functions DON'T allow for re-writing the values (contrary to documentation)
        self.url = util.NormalizeUrl(self.url)
        self.title = util.TrimString(self.title)
        if not self.title:
            self.title = self.url 
        self.title = unicode(self.title, 'utf8')
        
        rg = urlsplit(self.url)
        if rg[1] in Map.blackList:
            raise util.Error("Can't create link to domain: %s" % rg[1], status="Fail/Domain")
    
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
    
    @classmethod
    def TopPages(cls):
        return cls.ss.Best();
    
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
    
    def Comments(self):
        return self.comment_set.fetch(100)
    
    def Shared(self):
        self.shareCount = self.shareCount + 1
        self.put()
        self.ss.Update(self, self.scoreShare)
        
    def Viewed(self):
        self.viewCount = self.viewCount + 1
        self.put()
        self.ss.Update(self, self.scoreView)
        
    def JSON(self):
        obj = {'url':self.url, 'id':self.GetId(), 'title':self.title,
               'viewed':self.viewCount, 'shared':self.shareCount, 'created':self.dateCreated}
        rgComments = [];
        for comment in self.Comments():
            c = {'comment': comment.comment}
            if comment.username:
                c['user'] = comment.username
            if comment.tags:
                c['tags'] = comment.tags
            rgComments.append(c)
        if len(rgComments) > 0: 
            obj['comments'] = rgComments
        return obj

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
    username = db.StringProperty()
    comment = db.StringProperty()
    tags = db.StringProperty()
    map = db.ReferenceProperty(Map)
    dateCreated = db.DateTimeProperty(auto_now=True)
    
    def __init__(self, *args, **kw):
        db.Model.__init__(self, *args, **kw)
        
        self.username = util.TrimString(self.username)
        self.comment = util.TrimString(self.comment)
        self.tags = util.TrimString(self.tags)
        
    def TagList(self):
        return self.tags.split(",")
    