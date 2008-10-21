from google.appengine.ext import db
from django.shortcuts import render_to_response
from util import *
from timescore.models import ScoreSet, hrsMonth

import logging
from sys import exc_info
from urlparse import urlsplit
import re
from datetime import datetime
import pickle

class Map(db.Model):
    ss = ScoreSet.GetSet("map")
    
    # Relative scores for user interactions
    scoreComment = 2
    scoreView = 1
    scoreShare = 3
    
    # TODO: Add a database model for blacklisted domains
    blackList = {'g02.me':True, 'www.g02.me': True, 'localhost:8080': True, 'tinyurl.com': True}
    
    url = db.StringProperty(required=True)
    title = db.StringProperty()
    dateCreated = db.DateTimeProperty()
    viewCount = db.IntegerProperty(default=0)
    shareCount = db.IntegerProperty(default=0)
    sTags = db.TextProperty()
    
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
        dateCreated = datetime.now()
        id = Globals.IdNext()
        map = Map(key_name=Map.KeyFromId(id), url=url, title=title, dateCreated=dateCreated)
        map.x = 1
        return map
    
    def put(self):
        self.ReifyTags()
        self.sTags = unicode(pickle.dumps(self.tags), 'ascii')
        db.Model.put(self)
        
    def ReifyTags(self):
        if hasattr(self, 'tags'):
            return;

        try:
            self.tags = pickle.loads(str(self.sTags))
        except:
            self.tags = {}
        
    def AddTags(self, rgTags):
        self.ReifyTags()
        for tag in rgTags:
            if not tag in self.tags:
                self.tags[tag] = 0
            self.tags[tag] = self.tags[tag] + 1
        self.put()
        
    def TopTags(self, limit=10):
        # Return to top 10 tags (by use) for this url
        self.ReifyTags()
        a = [(tag, self.tags[tag]) for tag in self.tags]
        a.sort(lambda x,y: y[1]-x[1])
        aT = [a[i][0] for i in range(min(len(a), limit))]
        aT.sort()
        return aT
            
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
        return cls.ss.Best()
    
    @classmethod
    def TopJSON(cls):
        return {'popular':[score.model.JSON() for score in cls.ss.Best() if score.ModelExists]}
    
    def GetId(self):
        return self.key().name()[2:]
    
    def GetDict(self):
        return {'host':local.stHost,
                'id':self.GetId(),
                'url':self.url,
                'title':self.title
                }
        
    def AddComment(self, username='', comment='', tags=''):
        comm = Comment.Create(map=self, username=username, comment=comment, tags=tags)
        comm.put()
        self.ss.Update(self, self.scoreComment)
        
    def CommentCount(self):
        # BUG: Will max out at 100 comments
        return len(self.Comments())
    
    def Comments(self, limit=100):
        # Just return "true" comments (not sharing events) - and prune comments for deleted models
        comments = self.comment_set.order('-dateCreated').fetch(limit)
        return [comment for comment in comments if comment.MapExists() and not comment.comment.startswith('__')]
    
    def Shared(self):
        self.shareCount = self.shareCount + 1
        self.put()
        self.ss.Update(self, self.scoreShare)
        # Overload the comment to record when a (registered user) shares a URL
        self.AddComment(username=local.username, comment="__share")
        
    def Viewed(self):
        self.viewCount = self.viewCount + 1
        self.put()
        self.ss.Update(self, self.scoreView)
        
    def JSON(self):
        obj = {'url':self.url, 'id':self.GetId(), 'title':self.title,
               'viewed':self.viewCount, 'shared':self.shareCount, 'created':self.dateCreated,
               'scores':self.ss.ScoresJSON(self)
               }
        rgComments = []
        for comment in self.Comments():
            rgComments.append(comment.JSON())
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
    dateCreated = db.DateTimeProperty()
    
    @classmethod
    def Create(cls, map, username='', comment='', tags=''):
        username = TrimString(username)
        userid = local.userid
        comment = TrimString(comment)
        tags = TrimString(tags)
        dateCreated = datetime.now()
        
        if tags == '' and comment == '':
            raise Error("Empty comment")
        
        com = Comment(map=map, username=username, userid=userid, comment=comment, tags=tags, dateCreated=dateCreated)
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
        
    @classmethod
    def ForUser(cls, username):
        comments = Comment.gql("WHERE username = :username ORDER BY dateCreated DESC", username=username)
        clist = []
        dup = set()
        for comment in comments:
            if not comment.MapExists():
                continue
            key = comment.map.GetId()
            if key in dup:
                continue
            dup.add(key)
            clist.append(comment)
        return clist
    
    @classmethod
    def ForUserJSON(cls, username):
        obj = {'user':username}
        rg = [comment.map.JSON() for comment in cls.ForUser(username)]
        if len(rg) > 0: 
            obj['urls'] = rg
        return obj
    
    def MapExists(self):
        obj = db.get(self.MapKey())
        return not obj is None
    
    def MapKey(self):
        return Comment.map.get_value_for_datastore(self)
        
    def TagList(self):
        return self.tags.split(",")
    
    def JSON(self):
        c = {'comment': self.comment}
        if self.username:
            c['user'] = self.username
        else:
            c['user'] = self.userid
        if self.tags:
            c['tags'] = self.tags
        c['created'] = self.dateCreated
        c['cid'] = self.key().id()
        return c
    
    @classmethod
    def BadComments(cls):
        comments = Comment.gql("WHERE comment = '' AND tags = ''")
        return comments.fetch(100)
    
    @classmethod
    def Broken(cls, limit=1000):
        # Return the broken links
        comments = db.Query(Comment).order('-dateCreated')
        return [comment for comment in comments.fetch(limit) if not comment.MapExists()]