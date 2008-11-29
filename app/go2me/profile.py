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
    regUsername = re.compile(r"^[a-zA-Z0-9_\.\-]{1,20}$")
    
    # Account identifiers
    user = db.UserProperty(required=True)               # Google account
    username = db.StringProperty(required=True)         # Go2.me nickname
    keyCrypt = db.StringProperty()                      # Per-user encryption key
    dateCreated = db.DateTimeProperty()
    userTwitter = db.StringProperty()
    passTwitterCipher = db.StringProperty()             # E(key, passPlain)
    keyFriendFeed = db.StringProperty()                 # API Key for Friendfeed
    userAuthFirst = db.StringProperty()                 # Initial auth token for the creating user

    fBanned = db.BooleanProperty(default=False)
    fAdmin = db.BooleanProperty(default=False)
    
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
    
    @staticmethod
    def FindOrCreate(user, username):
        # First try lookup by username (and create if not taken)
        profile = None
        if username:
            Profile.RequireValidUsername(username)
            profile = Profile.get_or_insert(key_name='U:' + username, user=user, username=username, userAuthFirst=local.requser.UserId(),
                      dateCreated=local.dtNow)

        if not profile or profile.user != user:
            # username and user do not match - switch to the user's account - ignore username
            profile = Profile.gql('WHERE user = :1', user).get()
        return profile
    
    @staticmethod
    def Lookup(username):
        profile = Profile.gql('WHERE username = :1', username).get()
        return profile
    
    @staticmethod
    def RequireValidUsername(username):
        if not Profile.regUsername.match(username):
            raise Error("Invalid nickname: %s" % username, 'Fail/Auth')

