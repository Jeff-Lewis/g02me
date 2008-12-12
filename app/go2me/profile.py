from google.appengine.ext import db
from google.appengine.api import memcache, images

from django import forms

from util import *
from timescore.models import ScoreSet, hrsMonth, hrsWeek
import settings
from templatetags import custom

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
    regDate = re.compile(r"^\s*(?P<mon>\d{1,2})\s*(?:\.|-|/)\s*(?P<day>\d{1,2})\s*(?:\.|-|/)\s*(?P<year>\d{2}|\d{4})\s*$")
    
    # Account identifiers
    user = db.UserProperty(required=True)               # Google account
    username = db.StringProperty(required=True)         # Go2.me nickname
    keyCrypt = db.StringProperty()                      # Per-user encryption key
    dateCreated = db.DateTimeProperty()
    userAuthFirst = db.StringProperty()                 # Initial auth token for the creating user
    
    fBanned = db.BooleanProperty(default=False)
    fAdmin = db.BooleanProperty(default=False)
    
    # Personal/profile information
    dateBirth = db.DateProperty()
    sFullname = db.StringProperty(default='')
    sLocation = db.StringProperty(default='')
    urlHome = db.StringProperty(default='')
    sAbout = db.TextProperty(default='')
    img_full = db.BlobProperty()
    img_med = db.BlobProperty()
    img_thumb = db.BlobProperty()
    
    """
    Future Properties
    shareCount = db.IntegerProperty(default=0)
    commentCount = db.IntegerProperty(default=0)
    userTwitter = db.StringProperty()
    passTwitterCipher = db.StringProperty()             # E(key, passPlain)
    keyFriendFeed = db.StringProperty()                 # API Key for Friendfeed
    """
    
    @staticmethod
    def FindOrCreate(user, username, userid):
        profile = Profile.gql('WHERE user = :1', user).get()
        if profile:
            return profile
    
        # User creates Google Account before selecting a username - try the nickname
        if username:
            Profile.RequireValidUsername(username)
            profile = Profile.get_or_insert(key_name='U:' + username, user=user, username=username, userAuthFirst=userid,
                      dateCreated=local.dtNow)

        # If username was already used, we can't return another user's profile.  Try to create a unique one
        # from the account's nickname.
        if profile is None or profile.user != user:
            username = re.sub('@.*', '', user.nickname())
            profile = Profile.get_or_insert(key_name='U:' + username, user=user, username=username, userAuthFirst=userid,
                      dateCreated=local.dtNow)
            if profile.user != user:
                return None

        return profile
    
    @staticmethod
    def Lookup(username):
        profile = Profile.gql('WHERE username = :1', username).get()
        return profile
    
    @staticmethod
    def RequireValidUsername(username):
        if not Profile.regUsername.match(username):
            raise Error("Invalid nickname: %s" % username, 'Fail/Auth')
        
    def IsValid(self):
        return self.dateBirth is not None
        
    def GetForm(self):
        mpForm = {
            'username': self.username,
            'sFullname': self.sFullname,
            'dateBirth': (self.dateBirth and self.dateBirth.strftime("%m/%d/%Y")) or '',
            'sLocation': self.sLocation,
            'sAbout': self.sAbout,
            'urlHome': self.urlHome
            }
        return mpForm

    def SetForm(self, mpForm):
        # TODO: Since we're not on Django 1.0 - can't use the nifty forms package.
        try:
            if not self.username:
                sUser = mpForm['username'].strip()
                if not self.regUsername.match(sUser):
                    raise Error("Invalid username: %s" % sUser, obj={'error_field':'username'})
                self.username = sUser
            else:
                mpForm['username'] = self.username

            if mpForm['dateBirth']:
                m = self.regDate.match(mpForm['dateBirth'])
                if not m:
                    raise Error(sValidDate, obj={'error_field':'dateBirth'})
                yr = int(m.group('year'))
                if yr < 100:
                    yr += 1900;
                self.dateBirth = datetime.date(yr, int(m.group('mon')), int(m.group('day')))
                
                ddt = local.dtNow.date() - self.dateBirth
                if ddt.days < 365*13:
                    raise Error(sAgeRequirement % (custom.SAgeDdt(ddt), (settings.sSiteName)), obj={'error_field':'dateBirth'}) 
            else:
                raise Error(sValidDate, obj={'error_field':'dateBirth'})
            
            self.sFullname = mpForm['sFullname'].strip()
            self.sLocation = mpForm['sLocation'].strip()
            sURL = mpForm['urlHome'].strip()
            if sURL == '':
                self.urlHome = ''
            else:
                AddToResponse({'error_field':'urlHome'})
                self.urlHome = NormalizeUrl(sURL)
                AddToResponse({'error_field':''})
            self.sAbout = mpForm['sAbout'].strip()
            
            try:
                if 'img' in local.req.FILES:
                    image = local.req.FILES['img']['content']
                    self.img_full = image
                    image = images.Image(image)
                    
                    image.resize(75, 75)
                    self.img_med = image.execute_transforms(output_encoding=images.PNG)
                    image.resize(25, 25)
                    self.img_thumb = image.execute_transforms(output_encoding=images.PNG)
            except:
                self.img_full = None
                self.img_med = None
                self.img_thumb = None
                raise Error("Error processing uploaded image")
            
            self.put()
            return True
        except Error, e:
            logging.info("Error: %r" % e.obj)
            AddToResponse(e.obj)
        except Exception, e:
            logging.info("Unknown error: %r" % e)
            AddToResponse({'message': "Application Error"})
        return False
    
sValidDate = "Please enter a valid date (M/D/YYYY)"
sAgeRequirement = "You were born %s - you must be 13 years old to use %s"