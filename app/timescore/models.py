from google.appengine.ext import db
from datetime import datetime
import logging
import math

class ScoreSet(db.Model):
    """ Configuration object for a collection of (comparable) scores.
    halfLife is a list of integers (unit=hours)
    
    Once initialized a ScoreSet should not be changed.
    """
    name = db.StringProperty(required=True)
    halfLives = db.ListProperty(int)
    
    def __init__(self, *args, **kw):
        db.Model.__init__(self, *args, **kw)
        if len(self.halfLives) == 0:
            self.halfLives = [hrsDay, hrsWeek, hrsMonth, hrsYear]
    
    @classmethod
    def GetSet(cls, name):
        ss = ScoreSet.get_or_insert(name, name=name)
        return ss
    
    def Update(self, model, value, dt=datetime.now()):
        logging.info("SS - Update")
        scores = Score.gql('WHERE name = :name AND model = :model', name=self.name, model=model)
        if scores.count() == 0:
            for hrs in self.halfLives:
                logging.info("SS - creating %d" % hrs)
                s = Score(name=self.name, hrsHalf=hrs, model=model)
                s.Update(value, dt)
            return
        
        logging.info("SS - updating scores")
        
        for s in scores:
            s.Update(value, dt)

class Score(db.Model):
    dtBase = datetime(2000,1,1)

    name = db.StringProperty(required=True)
    hrsHalf = db.IntegerProperty(required=True)
    S = db.FloatProperty(default=1.0)
    LogS = db.FloatProperty(default=0.0)
    hrsLast = db.FloatProperty(default=0.0)
    model = db.ReferenceProperty(required=True)
    
    def Update(self, value, dt=datetime.now()):
        value = float(value)
        k = 0.5 ** (1.0/self.hrsHalf)
        
        hrs = Score.Hours(dt)
        
        if hrs > self.hrsLast:
            self.S = (1-k) * value + (k ** (hrs - self.hrsLast)) * self.S
            self.hrsLast = hrs
        else:
            self.S += (1-k) * (k ** (self.hrsLast - hrs)) * value
            
        logging.info("Score: %f " % self.S)
            
        # Todo: handle positive and negative values
        self.LogS = math.log(self.S)/math.log(2) + self.hrsLast/self.hrsHalf
        self.put()
    
    @classmethod    
    def Hours(cls, dt1):
        ddt = dt1 - Score.dtBase
        hrs = ddt.days*24 + float(ddt.seconds)/60/60
        return hrs

# Constants
hrsDay = 24
hrsWeek = 7*24
hrsYear = 365*24+6
hrsMonth = hrsYear/12





    
