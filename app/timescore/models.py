from google.appengine.ext import db
from google.appengine.api import memcache

from datetime import datetime, timedelta
import logging
import math

import calc

import util

class ScoreSet(db.Model):
    """ Configuration object for a collection of (comparable) scores.
    halfLife is a list of integers (unit=hours)
    
    Once initialized a ScoreSet should not be changed.
    """
    # BUG: No need to persist ScoreSet's in the database!
    name = db.StringProperty(required=True)
    halfLives = db.ListProperty(int)
    
    @classmethod
    def GetSet(cls, name, halfLives=None):
        if halfLives is None:
            halfLives = [hrsDay, hrsWeek, hrsMonth, hrsYear]
        ss = ScoreSet.get_or_insert(name, name=name, halfLives=halfLives)
        return ss
    
    def Update(self, model, value, dt=None, tags=None):
        if dt is None:
            dt = util.local.dtNow
        scores = self.ScoresForModel(model)
        if len(scores) == 0:
            scores = []
            for hrs in self.halfLives:
                s = Score.Create(name=self.name, hrsHalf=hrs, model=model, tags=tags)
                scores.append(s)
        
        for s in scores:
            s.Update(value, dt, tags=tags)
            
    def Best(self, hrsHalf=24, limit=50, tag=None):
        if tag:
            scores = Score.gql('WHERE name = :name AND hrsHalf = :hrsHalf AND tag = :tag ORDER BY LogS DESC', name=self.name, hrsHalf=hrsHalf, tag=tag)
        else:
            scores = Score.gql('WHERE name = :name AND hrsHalf = :hrsHalf ORDER BY LogS DESC', name=self.name, hrsHalf=hrsHalf)
        return scores.fetch(limit)
    
    def Broken(self, limit=100):
        # Return the broken links
        scores = Score.gql('WHERE name = :name ORDER BY hrsLast DESC', name=self.name)
        return [score for score in scores.fetch(limit) if not score.ModelExists()]

    def ScoresForModel(self, model, limit=5):
        return Score.gql('WHERE name = :name AND model = :model', name=self.name, model=model).fetch(limit)
    
    def ScoresNamed(self, model):
        scores = self.ScoresForModel(model)
        obj = {}
        for score in scores:
            obj[self.HalfName(score.hrsHalf)] = score.ScoreNow()
        return obj
    
    def DeleteScores(self, model):
        scores = self.ScoresForModel(model)
        for score in scores:
            score.delete()
    
    @classmethod
    def HalfName(cls, hrs):
        return {hrsDay:'day', hrsWeek:'week', hrsMonth:'month', hrsYear:'year'}.get(hrs, str(hrs))

class Score(db.Model):
    """
    Each Score accumulates time-based event values and associates them with an external Model
    
    Each score can be queried by name, and optionally a string tag that can be associated with each
    score.
    """
    dtBase = datetime(2000,1,1)

    name = db.StringProperty(required=True)
    hrsHalf = db.IntegerProperty(required=True)
    S = db.FloatProperty(required=True)
    LogS = db.FloatProperty(required=True)
    hrsLast = db.FloatProperty(required=True)
    model = db.ReferenceProperty(required=True)
    tag = db.StringListProperty()
    
    @classmethod
    def Create(cls, name=None, hrsHalf=None, model=None, tags=None):
        sc = calc.ScoreCalc(hrsHalf)
        score = Score(name=name, hrsHalf=hrsHalf, S=sc.S, LogS=sc.LogS, hrsLast=sc.tLast, model=model, tag=tags)
        logging.info("Score created (%r): %d, %d"% (hrsHalf, score.S, score.LogS))
        return score
    
    def Update(self, value, dt=None, tags=None):
        sc = calc.ScoreCalc(tHalf=self.hrsHalf, value=self.S, tLast=self.hrsLast)
        if dt is None:
            dt = util.local.dtNow
            
        sc.Increment(value, Score.Hours(dt))

        self.S = sc.S
        self.LogS = sc.LogS
        self.hrsLast = sc.tLast
        
        # Replace tags if given
        if tags is not None:
            self.tag = tags;
        
        self.put()
        logging.info("Update complete: %r" % self)
        
    def ScoreNow(self, dt=None):
        sc = calc.ScoreCalc(tHalf=self.hrsHalf, value=self.S, tLast=self.hrsLast)
        if dt is None:
            dt = util.local.dtNow
        sc.Increment(0, Score.Hours(dt))
        return sc.S
    
    @staticmethod    
    def Hours(dt1):
        ddt = dt1 - Score.dtBase
        hrs = ddt.days*24 + float(ddt.seconds)/60/60
        return hrs
    
    def DateLast(self):
        ddt = timedelta(self.hrsLast/24)
        dt = Score.dtBase + ddt
        return dt
    
    def ModelExists(self):
        obj = db.get(self.ModelKey())
        return not obj is None
    
    def ModelKey(self):
        return Score.model.get_value_for_datastore(self)
    
# Constants
hrsDay = 24
hrsWeek = 7*24
hrsYear = 365*24+6
hrsMonth = hrsYear/12

# --------------------------------------------------------------------
# Rate limiter helper
# --------------------------------------------------------------------
class Rate(object):
    # All date values must occur after this baseline date
    dtBase = datetime(2008,10,27)

    def __init__(self, cMax, secs):
        # Max rate allowed
        self.SMax = float(cMax) / secs 
        self.k = 0.5 ** (1.0/secs)
        self.secsLast = 0
        self.S = 0.0
        
    def FExceeded(self, value=1.0, dt=None):
        """
        Returns true if all prior calls exceed the established rate (always returns False on first call).
        Current rate is updated as a side effect.
        """
        if dt is None:
            dt = util.local.dtNow
        secs = self.Secs(dt)
        
        # Ignore times in the past
        if secs < self.secsLast:
            return False
        
        self.S = (self.k ** (secs - self.secsLast)) * self.S
        self.secsLast = secs
        
        f = self.S >= self.SMax
        
        self.S += (1-self.k) * value
        
        return f
    
    @staticmethod    
    def Secs(t1):
        dt = t1 - Rate.dtBase
        secs = dt.days*24*60*60 + dt.seconds
        return secs

