from google.appengine.ext import db
from datetime import datetime

class ScoreSet(db.Model):
    """ Configuration object for a collection of (comparable) scores.
    halfLife is a list of integers (unit=hours)
    
    Once initialized a ScoreSet should not be changed.
    """
    name = db.StringProperty(required=True)
    halfLives = db.ListProperty(int)
    
    if halfLives == None:
        halfLives = [hrsDay, hrsWeek, hrsMonth, hrsYear]
    
    @classmethod
    def GetSet(cls, name):
        ss = ScoreSet.get_or_insert(name, name=name)
        return ss
    
    def Update(self, model, dt, value):
        scores = Score.gql('WHERE name = :name AND model = :model', name=name, model=model)
        if scores.count() == 0:
            for hrs in self.halfLives:
                s = Score(name=name, hrsHalf=hrs, model=model)
                s.Update(dt, value)
            return
        
        for s in scores:
            s.Update(dt, value)

class Score(db.Model):
    dtBase = datetime.datetime(2000,1,1)

    name = dbStringProperty(required=True)
    hrsHalf = db.IntegerProperty(required)
    S = db.FloatProperty(default=1)
    LogS = db.FloatProperty(default=0)
    hrsLast = db.DateTimeProperty(auto_now=True)
    model = db.ReferenceProperty(required=True)
    
    def Update(self, dt, value):
        k = 0.5 ** (1.0/hrsHalf)
        
        hrs = Score.Hours(dt)
        
        if hrs > self.hrsLast:
            self.S = (1-k) * value + (k ** (hrs - self.hrsLast)) * self.S
            self.hrsLast = hrs
        else:
            self.S += (1-k) * (k ** (self.hrsLast - hrs)) * value
            
        """ Todo: handle positive and negative values
        self.LogS = math.log(self.S)/math.log(2) + this.hrsLast/self.hrsHalf
        self.put()
    
    @classmethod    
    def Hours(cls, dt1):
        ddt = dt1 - Score.dtBase
        hrs = ddt.days*24 + float(ddt.seconds)/60/60
        return hrs

# Constants
hrsDay = 24
hrsWeek = 7*24
hrsMonth = 30*24
hrsYear = 365*24


    
