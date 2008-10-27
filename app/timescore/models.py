from google.appengine.ext import db
from datetime import datetime, timedelta
import logging
import math

class ScoreSet(db.Model):
    """ Configuration object for a collection of (comparable) scores.
    halfLife is a list of integers (unit=hours)
    
    Once initialized a ScoreSet should not be changed.
    """
    name = db.StringProperty(required=True)
    halfLives = db.ListProperty(int)
    
    @classmethod
    def GetSet(cls, name, halfLives=None):
        if halfLives is None:
            halfLives = [hrsDay, hrsWeek, hrsMonth, hrsYear]
        ss = ScoreSet.get_or_insert(name, name=name, halfLives=halfLives)
        return ss
    
    def Update(self, model, value, dt=datetime.now(), tags=None):
        scores = self.ScoresForModel(model)
        if scores.count() == 0:
            scores = []
            for hrs in self.halfLives:
                s = Score(name=self.name, hrsHalf=hrs, model=model, tags=tags)
                scores.append(s)
        
        for s in scores:
            s.Update(value, dt, tags=tags)
            
    def Best(self, hrsHalf=24, limit=100, tag=None):
        if tag:
            scores = Score.gql('WHERE name = :name AND hrsHalf = :hrsHalf AND tag = :tag ORDER BY LogS DESC', name=self.name, hrsHalf=hrsHalf, tag=tag)
        else:
            scores = Score.gql('WHERE name = :name AND hrsHalf = :hrsHalf ORDER BY LogS DESC', name=self.name, hrsHalf=hrsHalf)
        return scores.fetch(limit)
    
    def Broken(self, limit=1000):
        # Return the broken links
        scores = Score.gql('WHERE name = :name ORDER BY hrsLast DESC', name=self.name)
        return [score for score in scores.fetch(limit) if not score.ModelExists()]

    def ScoresForModel(self, model):
        return Score.gql('WHERE name = :name AND model = :model', name=self.name, model=model)
    
    def ScoresJSON(self, model):
        scores = self.ScoresForModel(model)
        obj = {}
        for score in scores:
            obj[self.HalfName(score.hrsHalf)] = score.ScoreNow()
        return obj
    
    @classmethod
    def HalfName(cls, hrs):
        return {hrsDay:'day', hrsWeek:'week', hrsMonth:'month', hrsYear:'year'}.get(hrs, str(hrs))
        
class Score(db.Model):
    # All date values must occur after this baseline date 1/1/2000
    dtBase = datetime(2000,1,1)

    name = db.StringProperty(required=True)
    hrsHalf = db.IntegerProperty(required=True)
    S = db.FloatProperty(default=1.0)
    LogS = db.FloatProperty(default=0.0)
    hrsLast = db.FloatProperty(default=0.0)
    model = db.ReferenceProperty(required=True)
    tag = db.StringListProperty()
    
    def Update(self, value, dt=datetime.now(), tags=None):
        value = float(value)
        k = 0.5 ** (1.0/self.hrsHalf)
        
        hrs = Score.Hours(dt)
        
        if hrs > self.hrsLast:
            self.S = (1-k) * value + (k ** (hrs - self.hrsLast)) * self.S
            self.hrsLast = hrs
        else:
            self.S += (1-k) * (k ** (self.hrsLast - hrs)) * value
            
        #logging.info("Score: %f " % self.S)
            
        # Todo: handle positive and negative values
        self.LogS = math.log(self.S)/math.log(2) + self.hrsLast/self.hrsHalf
        
        if tags is not None:
            self.tag = tags;
        
        self.put()
        
    def ScoreNow(self, dt=datetime.now()):
        hrs = Score.Hours(dt)
        k = 0.5 ** (1.0/self.hrsHalf)
        return (k ** (hrs - self.hrsLast)) * self.S
    
    @classmethod    
    def Hours(cls, dt1):
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





    