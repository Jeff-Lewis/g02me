from google.appengine.ext import db
from google.appengine.api import memcache

from util import *
from timescore.models import ScoreSet, hrsMonth, hrsWeek
import settings

import logging
from urlparse import urlsplit
import re
import pickle

class Profile(db.Model):
    """
    User Profile information for a logged-in user
    """
    ss = ScoreSet.GetSet("karma", [hrsWeek, hrsMonth])
    
    # Account identifiers
    user = db.UserProperty()                # Google account
    username = db.StringProperty()          # Go2.me nickname
    keyCrypt = db.StringProperty()               # Per-user encryption key
    dateCreated = db.DateTimeProperty()
    userTwitter = db.StringProperty()
    passTwitterCipher = db.StringProperty() # E(key, passPlain)
    keyFriendFeed = db.StringProperty()     # API Key for Friendfeed
    userAuthFirst = db.StringProperty()     # Initial auth token for the creating user

    fBan = db.BooleanProperty(default=False)
    
    # Personal/profile information
    dateBirth = db.DateProperty()
    sLocation = db.StringProperty()
    sCity = db.StringProperty()
    sState = db.StringProperty()
    sCountry = db.StringProperty()
    urlHome = db.StringProperty()
    sAbout = db.StringProperty()
    shareCount = db.IntegerProperty(default=0)
    commentCount = db.IntegerProperty(default=0)
    sTags = db.TextProperty()

    fBan = db.BooleanProperty(default=False)
    
    @classmethod
    def Create(cls):
        local.requser.Require('write', 'user')
        profile = Profile(user=local.requser.user, username=local.requser.username, userAuthFirst=local.requser.UserId(),
                  dateCreated=local.dtNow)
        return profile

    @classmethod
    def Lookup(cls, user):
        profile = Profile.gql('WHERE user = :1', user).get()
        return profile
