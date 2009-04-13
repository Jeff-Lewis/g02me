from google.appengine.ext import db
from google.appengine.api import memcache

from util import *
from timescore.models import ScoreSet, hrsMonth
import settings
import templatetags.custom

import logging
from urlparse import urlsplit
import re
import pickle
import urllib
import hashlib

""" ------------------------------------------------------------------
Map model (a URL link).
-------------------------------------------------------------------"""

class Map(db.Model):
    ss = ScoreSet.GetSet("map")
    
    # Relative scores for user interactions
    scoreView = 1
    scoreFavorite = 2
    scoreShare = 2
    scoreComment = 7
    
    # Schema version for conversion of old models
    schema = db.IntegerProperty(default=2)
    dateCreated = db.DateTimeProperty()

    url = db.StringProperty(required=True)
    title = db.StringProperty()
    userAuthFirst = db.StringProperty()
    usernameCreator = db.StringProperty()
    
    # Number of unique viewers, sharers, and commenters
    viewCount = db.IntegerProperty(default=0)
    shareCount = db.IntegerProperty(default=0)
    commentCount = db.IntegerProperty(default=0)

    # (Pickled) dictionary of tag counts applied to this model
    sTags = db.TextProperty()
    
    # Banned models are not deleted, but they do not get scored
    fBan = db.BooleanProperty(default=False)
    
    # (Pickled) list of usernames subscribing to this link
    sSubscribers = db.TextProperty()
    
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
        
        CheckBlacklist(rg[1])       

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
        
    def RemoveTags(self, rgTags):
        self.ReifyTags()
        for tag in rgTags:
            # Ignore empty or uncounted tags
            if tag == '' or tag not in self.tags:
                continue
            self.tags[tag] = self.tags[tag] - 1
            if self.tags[tag] <= 0:
                del self.tags[tag]
        
    def TopTags(self, limit=20):
        # Return to top 20 tags (by use) for this url
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
    def TopPages(cls, tag=None, limit=50):
        return cls.ss.Best(tag=tag, limit=limit)
    
    @classmethod
    def TopJSON(cls, tag=None):
        return {'pages':[score.model.JSON() for score in cls.ss.Best(tag=tag) \
             if score.ModelExists() and not score.model.Banished()]}
    
    def GetId(self):
        return self.key().name()[2:]
    
    def TweetText(self):
        sSuffix = " - http://%s/%s" % (settings.sSiteHost, self.GetId())
        sText = self.title[:(140-len(sSuffix))]
        sText = urllib.quote(sText.encode('utf-8'))
        return sText + sSuffix
    
    def GetDict(self):
        return {'host':local.stHost,
                'id':self.GetId(),
                'url':self.url,
                'title':self.title
                }
        
    def AddComment(self, username='', comment='', tags=''):
        self.EnsureCommentCount()
        comm = Comment.Create(map=self, username=username, comment=comment, tags=tags)
        comm.put()

        # No scoring/counting/tag accumulation for banished URL's or meta-comments
        if self.Banished():
            return
        
        scoreUpdate = 0
        dComment = 0
        if local.requser.FAllow('score'):
            if comment == '__fave':
                if local.requser.FOnce('fave.%s' % self.GetId()):
                    scoreUpdate = self.scoreFavorite
            elif not comment.startswith('__'):
                if local.requser.FOnce('comment.%s' % self.GetId()):
                    scoreUpdate = self.scoreComment
                    dComment = 1

        self.AddTags(tags.split(','))

        self.commentCount += dComment
        self.put()
        
        # Need to call update in case the tag list changes
        self.ss.Update(self, scoreUpdate, dt=local.dtNow, tags=self.TopTags())
        
    def GetFavorite(self, username):
        if username == '':
            return None
        comments = self.comment_set
        comments.filter('comment =', '__fave').filter('username =', username)
        return comments.get()
    
    def Uniques(self):
        return self.viewCount
    
    def CommentCount(self):
        # Cache the comment count in the model
        if self.EnsureCommentCount():
            self.put()
        return self.commentCount
    
    def EnsureCommentCount(self):
        # Historical models do not have this attribute - rebuild it from query
        if self.commentCount is None:
            self.commentCount = len(self.Comments())
            return True
        return False
    
    def Comments(self, limit=250, dateSince=None):
        # Just return "true" comments (not sharing events)
        comments = self.comment_set
        if dateSince is not None:
            comments.filter('dateCreated >', dateSince)
        comments.order('dateCreated').fetch(limit)
        return [comment for comment in comments if not comment.comment.startswith('__')]
    
    def Shared(self):
        # Updates shared count if a unique user share
        # ALWAYS - puts() the Map to the database as a side effect
        if not self.is_saved():
            self.put()
        if local.requser.FAllow('share') and \
            (local.requser.FOnce('share.%s' % self.GetId()) or self.shareCount == 0):
            self.shareCount += 1
            self.put()
            
            if local.requser.FAllow('score') and not self.Banished():
                self.ss.Update(self, self.scoreShare, dt=local.dtNow, tags=self.TopTags())

            # Overload the comment to record when a (registered user) shares a URL
            # BUG: Don't record __share if user has already shared it
            if local.requser.username != '':
                self.AddComment(username=local.requser.username, comment="__share")
        
    def Viewed(self):
        if not local.requser.FOnce('view.%s' % self.GetId()):
            return
        self.viewCount += 1
        self.put()
        logging.info("Increased view count to: %d" % self.viewCount)
        if local.requser.FAllow('score') and not self.Banished():
            self.ss.Update(self, self.scoreView, dt=local.dtNow, tags=self.TopTags())
        
    def Creator(self):
        return self.usernameCreator
    
    def Href(self):
        return Href(self.url)
    
    def Domain(self):
        rg = urlsplit(self.url)
        sHost = rg[1].lower()
        return sHost
        
    def JSON(self, dateSince=None, sState="Active", sLocation=None):
        # JSON (object) format of Map data - filtered to new since dateSince
        obj = {'url':self.url,
               'urlShort': r"http://%s/%s" % (settings.sSiteHost, self.GetId()),
               'id':self.GetId(),
               'title':self.title,
               'viewed':self.viewCount,
               'shared':self.shareCount,
               'favorite': self.GetFavorite(local.requser.username) is not None,
               'commenters':self.CommentCount(),
               'created':self.dateCreated,
               'scores':self.ss.ScoresNamed(self),
               'tags':self.TopTags(),
               'dateRequest': local.dtNow,
               'presence':self.Presence(sState=sState, sLocation=sLocation),
               }
        if dateSince:
            obj['since'] = dateSince
        rgComments = []
        for comment in self.Comments(dateSince=dateSince):
            rgComments.append(comment.JSON())
        if len(rgComments) > 0: 
            obj['comments'] = rgComments
        return obj
    
    def ScoresNamed(self):
        return self.ss.ScoresNamed(self)
    
    def Ban(self, fBan=True):
        self.fBan = fBan;
        self.put()
        if fBan:
            self.ss.DeleteScores(self)
    
    def Banished(self):
        f = self.fBan is not None and self.fBan
        return f
    
    @RunInTransaction
    def Presence(self, dateComment=None, sState=None, sLocation=None):
        # This should be in a transaction!
        idT = 'map.pres.%s' % self.GetId()
        aPresence = memcache.get(idT)
        if aPresence is None:
            aPresence = {}
        dateLimit = local.dtNow - timedelta(minutes=1)
        uidSelf = Slugify(local.requser.uid)
        aPresence = [u for u in aPresence if u['dateLast'] > dateLimit and u['id'] != uidSelf]

        # Users that are not allowed update presence, can still retrieve it
        if not local.requser.FAllow('presence'):
            return aPresence
        
        if local.requser.profile and local.requser.profile.img_thumb:
            urlThumb = '/user/%s/picture_thumb' % local.requser.username
        else:
            urlThumb = '/images/picture_thumb.png'

        uSelf = {'id': uidSelf,
                 'username':local.requser.username,
                 'dateLast': local.dtNow,
                 'thumb': urlThumb,
                 }

        if sState:
            uSelf['state'] = sState
        if dateComment:
            uSelf['dateComment'] = dateComment
        if sLocation:
            uSelf['location'] = sLocation
        aPresence.insert(0, uSelf)
        memcache.set(idT, aPresence, 90)
        return aPresence
    
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
    
""" ------------------------------------------------------------------
Global application variables (stored in the database)
-------------------------------------------------------------------"""

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

""" ------------------------------------------------------------------
Comment model.
schema    changes
  2       subscribers added (not used)
  3       follow boolean 
-------------------------------------------------------------------"""

class Comment(db.Model):
    schemaCurrent = 3
    
    schema = db.IntegerProperty(default=schemaCurrent)
    dateCreated = db.DateTimeProperty()
    
    # Parent item - anchor link for this comment
    map = db.ReferenceProperty(Map)
    
    username = db.StringProperty()
    userAuth = db.StringProperty()
    comment = db.StringProperty()
    scope = db.StringProperty(default=None)
    fFollow = db.BooleanProperty(default=False)
    
    # Comma separated list
    tags = db.StringProperty()
    
    # List of usernames subscribing to this comment
    subscribers = db.StringListProperty()
    
    # Parts:                    1  2                              3         4  5 
    regComment = re.compile(r"^( *([a-zA-Z0-9_\.\-]{1,20}) *: *)?([^\[]*) *(\[(.*)\])? *$")
    
    @staticmethod
    def Create(map, username='', comment='', tags='', scope='__public'):
        local.requser.Require('write', 'comment')
        username = TrimString(username)
        userAuth = local.requser.UserId()
        comment = TrimString(comment)
        tags = TrimString(tags)
        dateCreated = local.dtNow
        fFollow = local.requser.FAllow('follow')
        
        if tags == '' and comment == '':
            raise Error("Comment and tags missing")

        com = Comment(map=map, username=username, userAuth=userAuth, comment=comment, tags=tags,
                      dateCreated=dateCreated, scope=scope, fFollow=fFollow)
        return com
    
    def Delete(self):
        # Delete the Comment and update the tag list in the Map
        try:
            self.map.RemoveTags(self.tags.split(','))
            self.map.EnsureCommentCount()
            self.map.put()
        except:
            pass
        self.delete();
        
    @staticmethod
    def Parse(sUsername, sComment):
        if sUsername != '':
            sComment = "%s: %s" % (sUsername, sComment)

        sComment = unicode(sComment, 'utf8')            
        m = Comment.regComment.match(sComment)
    
        if m == None:
            raise Error("Improperly formatted comment")
        
        # Parse tags
        if m.group(5):
            tags = re.sub(" *, *", ',', m.group(5)).strip()
            rTags = tags.split(',')
            rTags = [Slugify(tag) for tag in rTags if tag != '']
            tags = ','.join(rTags)
        else:
            tags = ''
        
        # Username    
        sUsername = m.group(2)
        if sUsername is None:
            sUsername = ''
            
        # Comment proper
        sComment = m.group(3)
        if sComment.startswith('__'):
            raise Error("Comments cannot begin with '__' (underscores)")

        # Users can begin a comment with a URL - don't treat it as a username field
        if sUsername == "http":
            sUsername = ''
            sComment = "http:" + sComment
        
        return {'username': sUsername,
                'comment': sComment,
                'tags': tags}
        
    @staticmethod
    def ForUser(username):
        comments = Comment.gql("WHERE username = :username ORDER BY dateCreated DESC", username=username)
        comments = comments.fetch(100)
        clist = []
        dup = set()
        for comment in comments:
            key = comment.MapKey()
            if key in dup:
                continue
            dup.add(key)
            # Cleanup comments from expunged Maps
            if not comment.MapExists():
                logging.warning("Removing orphaned comment for %s." % comment.MapKey())
                comment.delete()
                continue
            clist.append(comment)
            if len(clist) == 50:
                break;
        return clist
    
    def MapKey(self):
        return Comment.map.get_value_for_datastore(self)
    
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

    def AllowDelete(self):
        return self.username == '' or self.username == local.requser.username or local.requser.FAllow('admin')
    
    def DelKey(self):
        s = SSign('dk', self.key().id())
        return s
    
    def ID(self):
        return self.key().id()
    
    def JSON(self):
        c = {'comment': self.comment,
             'commentHTML': templatetags.custom.urlizecomment(EscapeHTML(self.comment))}
        if self.username:
            c['user'] = self.username
        if self.tags:
            c['tags'] = self.tags.split(',')
        c['created'] = self.dateCreated
        c['id'] = self.key().id()
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
                
    @staticmethod
    def Unscoped(limit=100):
        comments = Comment.gql("WHERE scope != '__public'");
        aUnscoped = []
        for comment in comments.fetch(limit):
            logging.info("scope: %s" % comment.scope)
            if comment.scope is None or comment.scope == '':
                aUnscoped.append(comment)
        return aUnscoped
