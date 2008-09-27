from google.appengine.ext import db

class Score(db.Model):
    type = db.StringProperty(required=True)
    S = db.FloatProperty(default=0)
    LogS = db.FloatProperty(default=0)
    updated = db.DateTimeProperty(auto_now=True)
    obj = db.ReferenceProperty()
    
