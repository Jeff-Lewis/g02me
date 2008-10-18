from google.appengine.ext import db
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from google.appengine.api import memcache
from util import *
from timescore.models import ScoreSet

import logging
from sys import exc_info
from urlparse import urlsplit
import re

class Map(db.Model):
    ss = ScoreSet.GetSet("map")
    
    # Relative scores for user interactions
    scoreComment = 2
    scoreView = 1
    scoreShare = 3
    
    # TODO: Add a database model for blacklisted domains
    blackList = {'g02.me':True, 'www.g02.me': True, 'localhost:8080': True}
    
    url = db.StringProperty(required=True)
    title = db.StringProperty()
    dateCreated = db.DateTimeProperty(auto_now=True)
    viewCount = db.IntegerProperty(default=0)
    shareCount = db.IntegerProperty(default=0)
    
    @classmethod
    def KeyFromId(cls, id):
        return "K:%s" % id
    
    @classmethod
    def Create(cls, url, title):
        url = NormalizeUrl(url)
        title = TrimString(title)
        if not title:
            title = url
        rg = urlsplit(url)
        if rg[1] in Map.blackList:
            raise Error("Can't create link to domain: %s" % rg[1], status="Fail/Domain")
        title = unicode(title, 'utf8')
        id = Globals.IdNext()
        map = Map(key_name=Map.KeyFromId(id), url=url, title=title)
        return map

    @classmethod
    def Lookup(cls, id):
        # just use id as key - more frequent than url lookup
        map = Map.get_by_key_name(Map.KeyFromId(id))
        return map
    
    @classmethod
    def FindUrl(cls, url):
        url = NormalizeUrl(url)
        query = db.Query(Map)
        query.filter('url =', url)
        map = query.get()
        return map
    
    @classmethod
    def FindOrCreateUrl(cls, url, title):
        map = Map.FindUrl(url)
        if map == None:
            map = Map.Create(url, title)
        map.Shared()
        return map
    
    @classmethod
    def TopPages(cls):
        return cls.ss.Best();
    
    def GetId(self):
        return self.key().name()[2:]
    
    def GetDict(self):
        return {'host':local.stHost,
                'id':self.GetId(),
                'url':self.url,
                'title':self.title
                }
        
    def AddComment(self, username, comment, tags):
        comm = Comment.Create(map=self, username=username, comment=comment, tags=tags)
        comm.put()
        self.ss.Update(self, self.scoreComment)
        
    def CommentCount(self):
        # TODO: Inefficient for large comment streams - loads all in memory
        return self.comment_set.count();
    
    def Comments(self):
        comments = self.comment_set
        comments.order('dateCreated')
        return comments.fetch(100)
    
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
        return IntToS64(cls.IdNameNext("current"))
    
    @classmethod
    def IdUserNext(cls):
        return cls.IdNameNext("user")
        
    @classmethod
    def IdNameNext(cls, name):
        glob = cls.get_or_insert(name)
        id = glob.idNext
        glob.idNext = glob.idNext + 1
        glob.put()
        return glob.idNext

class Comment(db.Model):
    username = db.StringProperty()
    userid = db.IntegerProperty()
    comment = db.StringProperty()
    tags = db.StringProperty()
    map = db.ReferenceProperty(Map)
    dateCreated = db.DateTimeProperty(auto_now=True)
    
    @classmethod
    def Create(cls, map, username="", comment="", tags=""):
        username = TrimString(username)
        userid = local.userid
        logging.info("assign comment to id %s" % local.userid)
        comment = TrimString(comment)
        tags = TrimString(tags)
        com = Comment(map=map, username=username, userid=userid, comment=comment, tags=tags)
        if username:
            local.username = username
        return com
    
    @classmethod
    def Parse(cls, st):
        reg = re.compile(r"^( *([a-zA-Z0-9_\.\-+]+) *: *)?([^\[]*) *(\[(.*)\])? *$")
        m = reg.match(st)
    
        if m == None:
            raise Error("Could not parse comment")
        
        
        if m.group(5):
            reg = re.compile(r" *, *")
            tags = reg.sub(",", m.group(5)).strip()
        else:
            tags = ""

        return {'username':m.group(2),
                'comment': m.group(3),
                'tags': tags}
        
    def TagList(self):
        return self.tags.split(",")
    