from datetime import datetime, timedelta
import math

class ScoreCalc():
    """
    Base functions for calculating half-life values from a stream of scoring events.
    
    Time units are abstract and zero-based.  The default half-life is 1 time unit.
    
    The Net score is valid at a particular time, tLast.  LogS is globally comparable as it is
    based at time t = 0.
    """
    
    def __init__(self, tHalf=1.0, value=0.0, tLast=0.0):
        """
        The score cannot be 0 - since we use Log(S) as a ordering key.  Instead, all scores
        are based at value = 1 at time = 0.  Negative log scores would occur for score values less
        than 1 at time = 0 - these are not allowed.
        """
        self.tHalf = float(tHalf)
        self.k = 0.5 ** (1.0/self.tHalf)
        self.S = 1.0
        self.tLast = 0.0
        self.Increment(value, tLast)
        
    def Increment(self, value=0.0, t=0.0):
        value = float(value)
        
        t = float(t)

        if t > self.tLast:
            self.S =  value + (self.k ** (t - self.tLast)) * self.S
            self.tLast = t
        else:
            self.S += (self.k ** (self.tLast - t)) * value
        
        try:    
            self.LogS = math.log(self.S)/math.log(2) + self.tLast/self.tHalf
        except:
            # On underflow - reset to minimum value - 1 at time zero
            self.S = 1.0
            self.tLast = 0.0
            self.LogS = 0.0

# --------------------------------------------------------------------
# Unit Tests
# --------------------------------------------------------------------
import unittest

class TestTimeScore(unittest.TestCase):
    def test_Base(self):
        sc = ScoreCalc()
        self.assertEqual(sc.S, 1.0)
        self.assertEqual(sc.tLast, 0)
        sc.Increment(0)
        self.assertEqual(sc.S, 1.0)
        
    def test_Incr(self):
        sc = ScoreCalc()
        sc.Increment(1)
        self.assertEqual(sc.S, 2.0)
        sc.Increment(1,1)
        self.assertEqual(sc.S, 2.0)
        
    def test_Series(self):
        sc = ScoreCalc()
        for t in range(1,10):
            sc.Increment(1, t)
        self.assertAlmostEqual(sc.S, 2.0, 2)

        for t in range(10,20):
            sc.Increment(1, t)
        self.assertAlmostEqual(sc.S, 2.0, 5)
        
    def test_Series24(self):
        sc = ScoreCalc(tHalf=24)
        
        for t in range(1,20):
            sc.Increment(1, t*24)
        self.assertAlmostEqual(sc.S, 2.0, 5)
        
    def test_Zero(self):
        sc = ScoreCalc(value=0)
        sLog = sc.LogS
        sc.Increment(0)
        self.assertEqual(sc.LogS, sLog)
        sc.Increment(0, 1)
        self.assertEqual(sc.LogS, sLog)

if __name__ == '__main__':
    unittest.main()
