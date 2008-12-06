from google.appengine.ext import db
from google.appengine.api import memcache

from django import forms

from util import *
from timescore.models import ScoreSet, hrsMonth, hrsWeek
import settings

import logging
from urlparse import urlsplit
import re
import pickle
import datetime

class Profile(db.Model):
    """
    User Profile information for a logged-in user
    """
    ss = ScoreSet.GetSet("karma", [hrsWeek, hrsMonth])
    regUsername = re.compile(r"^[a-zA-Z0-9_\.\-]{1,20}$")
    regDate = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
    mpFormFields = {'username':'username',
                    'birth':'dateBirth',
                    'home':'urlHome',
                    'loc':'sLocation',
                    'about':'sAbout'}
    
    # Account identifiers
    user = db.UserProperty(required=True)               # Google account
    username = db.StringProperty(required=True)         # Go2.me nickname
    keyCrypt = db.StringProperty()                      # Per-user encryption key
    dateCreated = db.DateTimeProperty()
    userTwitter = db.StringProperty()
    passTwitterCipher = db.StringProperty()             # E(key, passPlain)
    keyFriendFeed = db.StringProperty()                 # API Key for Friendfeed
    userAuthFirst = db.StringProperty()                 # Initial auth token for the creating user
    
    username.foobar = 1

    fBanned = db.BooleanProperty(default=False)
    fAdmin = db.BooleanProperty(default=False)
    
    # Personal/profile information
    dateBirth = db.DateProperty()
    sLocation = db.StringProperty(default='')
    urlHome = db.StringProperty(default='')
    sAbout = db.StringProperty(default='')
    img = db.BlobProperty()
    shareCount = db.IntegerProperty(default=0)
    commentCount = db.IntegerProperty(default=0)

    fBan = db.BooleanProperty(default=False)
    
    @staticmethod
    def FindOrCreate(user, username, userid):
        # First try lookup by username (and create if not taken)
        profile = None
        if username:
            Profile.RequireValidUsername(username)
            profile = Profile.get_or_insert(key_name='U:' + username, user=user, username=username, userAuthFirst=userid,
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

    def FForm(self, mpForm):
        # TODO: Since we're not on Django 1.0 - can't use the nifty forms package.
        try:
            if not self.username:
                sUser = mpForm['username'].strip()
                if not self.regUsername.match(sUser):
                    raise Error("Invalid username: %s" % sUser)
                self.username = mpForm.get('username', '')

            if mpForm.get('birth'):
                parts = self.regDate.match(mpForm['birth'])
                if not parts:
                    raise Error("Please enter a valid date (m/d/y)")
                yr = int(parts.group(3))
                if yr < 100:
                    yr += 1900;
                self.dateBirth = datetime.date(yr, int(parts.group(1)), int(parts.group(2)))
            
            self.sLocation = mpForm.get('loc', '')
            
            if mpForm.get('home'):
                pass
            self.put()
            return True
        except Error, e:
            logging.info("error %r" % e.obj['message'])
            AddToResponse({'error_message': e.obj['message']})
        except:
            AddToResponse({'error_message': "Application Error"})
        return False
    
    
