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
    blackList = set([settings.sSiteHost, 'www.%s' % settings.sSiteHost,
                 'tinyurl.com', 'www.tinyurl.com', 'bit.ly', 'is.gd', 'snurl.com',
                 'short.to', 'cli.gs', 'snipurl.com', 'ff.im', 'tr.im'])
    
    url = db.StringProperty(required=True)
    title = db.StringProperty()
    userAuthFirst = db.StringProperty()
    usernameCreator = db.StringProperty()
    dateCreated = db.DateTimeProperty()
    viewCount = db.IntegerProperty(default=0)
    shareCount = db.IntegerProperty(default=0)
    sTags = db.TextProperty()
    
    @classmethod
    def KeyFromId(cls, id):
        return "K:%s" % id
    
    @classmethod
    def Create(cls, url, title):
        local.requser.Require('write', 'share')
        url = NormalizeUrl(url)
        title = TrimString(title)
        userAuthFirst = local.requser.UserId()
        if not title:
            title = url
        rg = urlsplit(url)
        
        sError = """The %(siteName)s bookmarklet cannot be used to create links to %(host)s.
                To create a shortened link, visit a page NOT on %(host)s, then click the bookmarklet"""

        sHost = rg[1].lower()
        if sHost == settings.sSiteHost or sHost in settings.mpSiteAlternates or sHost.startswith('localhost'):
            raise Error(sError %
                {'siteName': settings.sSiteName, 'host':settings.sSiteHost}, 'Warning/Domain')
            
        if  sHost in Map.blackList:
            raise Error(sError %
                {'siteName': settings.sSiteName, 'host':sHost}, 'Fail/Domain')          

        title = unicode(title, 'utf8')
        dateCreated = local.dtNow
        id = Map.__IdNext()
        map = Map(key_name=Map.KeyFromId(id), url=url, title=title, userAuthFirst=userAuthFirst,
                  dateCreated=dateCreated, usernameCreator=local.requser.username)
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
        return {'pages':[score.model.JSON() for score in cls.ss.Best(tag=tag) if score.ModelExists()]}
    
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
        if local.requser.FAllow('score'):
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
        if not self.is_saved():
            self.put()
        if local.requser.FAllow('share') and \
            (local.requser.FOnce('map.%s' % self.GetId()) or self.shareCount == 0):
            self.shareCount = self.shareCount + 1
            self.put()
            
            if local.requser.FAllow('score'):
                self.ss.Update(self, self.scoreShare, dt=local.dtNow, tags=self.TopTags())

            # Overload the comment to record when a (registered user) shares a URL
            if local.requser.username != '' and local.requser.FAllow('comment'):
                self.AddComment(username=local.requser.username, comment="__share")
        
    def Viewed(self):
        if not local.requser.FOnce('map.%s' % self.GetId()):
            return
        self.viewCount = self.viewCount + 1
        self.put()
        if local.requser.FAllow('score'):
            self.ss.Update(self, self.scoreView, dt=local.dtNow, tags=self.TopTags())
        
    def Age(self):
        return SAgeReq(self.dateCreated)
    
    def Creator(self):
        return self.usernameCreator
    
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
        # Increment and return a global counter - starts at idMin
        glob = Globals._IdLookup(name, idMin)
        glob.idNext = glob.idNext + 1
        glob.put()
        return glob.idNext
    
    @staticmethod
    def IdGet(name, idMin=1):
        # Return value of a global counter - starts at idMin
        glob = Globals._IdLookup(name, idMin)
        return glob.idNext
    
    @staticmethod
    def _IdLookup(name, idMin):
        glob = Globals.get_by_key_name(name)
        if glob is None:
            glob = Globals(key_name=name)
        if glob.idNext < idMin-1:
            glob.idNext = idMin-1
        return glob        

class Comment(db.Model):
    username = db.StringProperty()
    userAuth = db.StringProperty()
    comment = db.StringProperty()
    tags = db.StringProperty()
    map = db.ReferenceProperty(Map)
    dateCreated = db.DateTimeProperty()
    
    regComment = re.compile(r"^( *([a-zA-Z0-9_\.\-]{1,20}) *: *)?([^\[]*) *(\[(.*)\])? *$")
    
    @staticmethod
    def Create(map, username='', comment='', tags=''):
        username = TrimString(username)
        userAuth = local.requser.UserId()
        comment = TrimString(comment)
        tags = TrimString(tags)
        dateCreated = local.dtNow
        
        if tags == '' and comment == '':
            raise Error("Empty comment")
        
        com = Comment(map=map, username=username, userAuth=userAuth, comment=comment, tags=tags, dateCreated=dateCreated)
        if username:
            local.requser.username = username
        return com
    
    def Delete(self):
        # Delete the Comment and update the tag list in the Map
        try:
            self.map.RemoveTags(self.tags.split(','))
        except:
            pass
        self.delete();
        
    @staticmethod
    def Parse(sUsername, sComment):
        if sUsername != '':
            sComment = "%s: %s" % (sUsername, sComment)
            
        m = Comment.regComment.match(sComment)
    
        if m == None:
            raise Error("Improperly formatted comment")
        
        if m.group(5):
            tags = re.sub(" *, *", ',', m.group(5)).strip()
            rTags = tags.split(',')
            rTags = [Slugify(tag) for tag in rTags if tag != '']
            tags = ','.join(rTags)
        else:
            tags = ''
            
        sUsername = m.group(2)
        if sUsername is None:
            sUsername = ''

        return {'username':sUsername,
                'comment': m.group(3),
                'tags': tags}
        
    @staticmethod
    def ForUser(username):
        comments = Comment.gql("WHERE username = :username ORDER BY dateCreated DESC", username=username)
        comments = comments.fetch(100)
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
            if len(clist) == 50:
                break;
        return clist
    
    @staticmethod
    def FUsernameUsed(sUsername):
        if sUsername == '':
            return False
        comment = Comment.gql("WHERE username = :username", username=sUsername).get()
        return comment is not None
    
    @staticmethod
    def ForUserJSON(username):
        obj = {'user':username}
        rg = [comment.map.JSON() for comment in Comment.ForUser(username)]
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
    
    def AllowDelete(self):
        return self.username == '' or self.username == local.requser.username
    
    def DelKey(self):
        s = SSign('dk', self.key().id())
        return s
    
    def JSON(self):
        c = {'comment': self.comment}
        if self.username:
            c['user'] = self.username
        if self.tags:
            c['tags'] = self.tags
        c['created'] = self.dateCreated
        if self.AllowDelete():
            c['delkey'] = self.DelKey()
        return c
    
    # Admin functions - used in /admin console -------------------
    
    @staticmethod
    def EmptyComments(limit=100):
        comments = Comment.gql("WHERE comment = '' AND tags = ''")
        return comments.fetch(limit)
    
    @staticmethod
    def Broken(limit=100):
        # Return the broken links
        comments = db.Query(Comment).order('-dateCreated')
        return [comment for comment in comments.fetch(limit) if not comment.MapExists()]
    
    @staticmethod
    def MissingCreator(limit=200):
        # Return the broken links
        comments = Comment.gql("WHERE comment = '__share' ORDER BY dateCreated DESC")
        aMissing = []
        for comment in comments.fetch(limit):
            if comment.map.usernameCreator is not None:
                continue
            ddt = abs(comment.dateCreated - comment.map.dateCreated)
            if ddt.days == 0 and ddt.seconds < 10:
                aMissing.append(comment)
        return aMissing
    
    @staticmethod
    def FixMissingCreators(comments):
        for comment in comments:
            if comment.map.usernameCreator is None and comment.username != '':
                comment.map.usernameCreator = comment.username
                comment.map.put()
    
    
    
    
    
    
    