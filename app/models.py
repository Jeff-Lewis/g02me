from google.appengine.ext import db
from google.appengine.api import memcache
from django.shortcuts import render_to_response

from util import *
from timescore.models import ScoreSet, hrsMonth
import settings

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
    # Avoid self-referential and URL ping-pong with known URL redirection sites
    blackList = set(['g02.me', 'www.g02.me', 'localhost:8080',
                 'tinyurl.com', 'www.tinyurl.com', 'bit.ly', 'is.gd', 'snurl.com',
                 'short.to'])
    
    url = db.StringProperty(required=True)
    title = db.StringProperty()
    userAuthFirst = db.StringProperty()
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
        userAuthFirst = RequireUserAuth()
        if not title:
            title = url
        rg = urlsplit(url)
        if rg[1] in Map.blackList:
            raise Error("Can't create link to domain: %s" % rg[1], status="Fail/Domain")
        title = unicode(title, 'utf8')
        dateCreated = datetime.now()
        id = Map.__IdNext()
        map = Map(key_name=Map.KeyFromId(id), url=url, title=title, userAuthFirst=userAuthFirst,
                  dateCreated=dateCreated)
        return map
    
    @staticmethod
    def __IdNext():
        return IntToSID(Globals.IdNameNext(settings.sMapName, settings.idMapBase))
    
    def put(self):
        self.ReifyTags()
        self.sTags = unicode(pickle.dumps(self.tags), 'ascii')
        db.Model.put(self)
        
    def ReifyTags(self):
        # TODO: Implement tags as class PickeDict(db.Property)
        if hasattr(self, 'tags'):
            return;

        try:
            self.tags = pickle.loads(str(self.sTags))
        except:
            self.tags = {}
        
    def AddTags(self, rgTags):
        self.ReifyTags()
        for tag in rgTags:
            # Ignore empty tags
            if tag == '':
                continue
            if not tag in self.tags:
                self.tags[tag] = 0
            self.tags[tag] = self.tags[tag] + 1
        self.put()
        
    def RemoveTags(self, rgTags):
        self.ReifyTags()
        for tag in rgTags:
            # Ignore empty or uncounted tags
            if tag == '' or tag not in self.tags:
                continue
            self.tags[tag] = self.tags[tag] - 1
            if self.tags[tag] <= 0:
                del self.tags[tag]
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
    def TopPages(cls, tag=None):
        return cls.ss.Best(tag=tag)
    
    @classmethod
    def TopJSON(cls, tag=None):
        return {'pages':[score.model.JSON() for score in cls.ss.Best(tag=tag) if score.ModelExists]}
    
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
        self.AddTags(tags.split(','))
        self.ss.Update(self, self.scoreComment, dt=local.dtNow, tags=self.TopTags())
        
    def CommentCount(self):
        # BUG: Will max out at 100 comments
        return len(self.Comments())
    
    def Comments(self, limit=100):
        # Just return "true" comments (not sharing events)
        comments = self.comment_set.order('-dateCreated').fetch(limit)
        return [comment for comment in comments if not comment.comment.startswith('__')]
    
    def Shared(self):
        # Updates shared count if a unique user share
        # ALWAYS - puts() the Map to the database as a side effect
        if not self._FLimitStats():
            self.shareCount = self.shareCount + 1
            self.put()
            self.ss.Update(self, self.scoreShare, dt=local.dtNow, tags=self.TopTags())
            self._FLimitStats()
        else:
            self.put()

        # Overload the comment to record when a (registered user) shares a URL
        if local.cookies['username'] != '':
            self.AddComment(username=local.cookies['username'], comment="__share")
        
    def Viewed(self):
        if self._FLimitStats():
            return
        self.viewCount = self.viewCount + 1
        self.put()
        self.ss.Update(self, self.scoreView, dt=local.dtNow, tags=self.TopTags())
        
    def _FLimitStats(self):
        try:
            ua = RequireUserAuth(True)
        except:
            return True
        
        try:
            id = self.GetId()
        except:
            return False

        if memcache.get('view.%s.%s' % (id, ua)):
            return True
        memcache.set('view.%s.%s' % (id, ua), True)
        return False

    def Age(self):
        return SAgeReq(self.dateCreated)
    
    def Href(self):
        return Href(self.url)
        
    def JSON(self):
        obj = {'url':self.url, 'id':self.GetId(), 'title':self.title,
               'viewed':self.viewCount, 'shared':self.shareCount, 'created':self.dateCreated,
               'scores':self.ss.ScoresJSON(self), 'tags':self.TopTags()
               }
        rgComments = []
        for comment in self.Comments():
            rgComments.append(comment.JSON())
        if len(rgComments) > 0: 
            obj['comments'] = rgComments
        return obj
    
    # Admin functions - for use in /shell or /admin ------------------
    # BUG: FindBadTagCounts does NOT WORK in shell - complains about undefined comment.tags property and
    # can't catch with try: block???

    @classmethod
    def FindEmptyTags(cls):
        maps = Map.all().fetch(1000)
        et = []
        for map in maps:
            map.ReifyTags()
            if '' in map.tags:
                et.append(map)
        return et
    
    @classmethod
    def FixEmptyTags(cls, maps):
        for map in maps:
            del map.tags['']
            map.put()
            
    @classmethod
    def FindBadTagCounts(cls):
        maps = Map.all().fetch(1000)
        et = []
        for map in maps:
            map.ReifyTags()
            tags = map.RecalcTags()
            if tags != map.tags:
                et.append(map)
        return et
    
    def STagDiff(self):
        self.ReifyTags()
        return "(tags) %r != (recalc) %r" % (self.tags, self.RecalcTags())
    
    def RecalcTags(self):
        comments = self.comment_set.fetch(1000)
        tags = {}
        for c in comments:
            try:
                for t in c.TagList():
                    t = t.encode('ascii')
                    if t == '':
                        continue
                    if not t in tags:
                        tags[t] = 0
                    tags[t] = tags[t] + 1
            except:
                print "RT EX: %r" % c.tags
        return tags
    
    @classmethod
    def FixTagCounts(cls, maps):
        for map in maps:
            map.tags = map.RecalcTags()
            map.put()
    

# TODO: Use a sharded counter   
class Globals(db.Model):
    idNext = db.IntegerProperty(default=0)
    s = db.StringProperty()
    
    @staticmethod
    def SGet(name, sDefault=""):
        # Global strings are constant valued - can only be updated in the store
        # via admin console 
        s = memcache.get('global.%s' % name)
        if s is not None:
            return s
        glob = Globals.get_or_insert(key_name=name, s=sDefault)
        # Since we can't bounce the server, force refresh each 60 seconds
        memcache.add('global.%s' % name, glob.s, time=60)
        return glob.s
        
    @staticmethod
    @RunInTransaction
    def IdNameNext(name, idMin=1):
        # Return a global counter - starts at idMin
        glob = Globals.get_by_key_name(name)
        if glob is None:
            glob = Globals(key_name=name)
        glob.idNext = glob.idNext + 1
        if glob.idNext < idMin:
            glob.idNext = idMin
        glob.put()
        return glob.idNext

class Comment(db.Model):
    username = db.StringProperty()
    userAuth = db.StringProperty()
    comment = db.StringProperty()
    tags = db.StringProperty()
    map = db.ReferenceProperty(Map)
    dateCreated = db.DateTimeProperty()
    
    @classmethod
    def Create(cls, map, username='', comment='', tags=''):
        username = TrimString(username)
        userAuth = RequireUserAuth(True)
        comment = TrimString(comment)
        tags = TrimString(tags)
        dateCreated = datetime.now()
        
        if tags == '' and comment == '':
            raise Error("Empty comment")
        
        com = Comment(map=map, username=username, userAuth=userAuth, comment=comment, tags=tags, dateCreated=dateCreated)
        if username:
            local.cookies['username'] = username
        return com
    
    def Delete(self):
        # Delete the Comment and update the tag list in the Map
        try:
            self.map.RemoveTags(self.tags.split(','))
        except:
            pass
        self.delete();
    
    @classmethod
    def Parse(cls, st):
        reg = re.compile(r"^( *([a-zA-Z0-9_\.\-+]+) *: *)?([^\[]*) *(\[(.*)\])? *$")
        m = reg.match(st)
    
        if m == None:
            raise Error("Could not parse comment")
        
        
        if m.group(5):
            tags = re.sub(" *, *", ',', m.group(5)).strip()
            rTags = tags.split(',')
            rTags = [Slugify(tag) for tag in rTags if tag != '']
            tags = ','.join(rTags)
        else:
            tags = ''

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
        try:
            return self.tags.split(',')
        except:
            return []

    def Age(self):
        return SAgeReq(self.dateCreated)
    
    def JSON(self):
        c = {'comment': self.comment}
        if self.username:
            c['user'] = self.username
        if self.tags:
            c['tags'] = self.tags
        c['created'] = self.dateCreated
        c['cid'] = self.key().id()
        return c
    
    # Admin functions - used in /admin console -------------------
    
    @classmethod
    def BadComments(cls):
        comments = Comment.gql("WHERE comment = '' AND tags = ''")
        return comments.fetch(100)
    
    @classmethod
    def Broken(cls, limit=1000):
        # Return the broken links
        comments = db.Query(Comment).order('-dateCreated')
        return [comment for comment in comments.fetch(limit) if not comment.MapExists()]