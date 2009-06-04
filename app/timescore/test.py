import calc
import models
import logging
import sys

import unittest

class TestTimeScore(unittest.TestCase):
    def test_Base(self):
        sc = calc.ScoreCalc()
        self.assertEqual(sc.S, 1.0)
        self.assertEqual(sc.tLast, 0)
        sc.Increment(0)
        self.assertEqual(sc.S, 1.0)
        
    def test_Incr(self):
        sc = calc.ScoreCalc()
        sc.Increment(1)
        self.assertEqual(sc.S, 2.0)
        sc.Increment(1,1)
        self.assertEqual(sc.S, 2.0)
        
    def test_Series(self):
        sc = calc.ScoreCalc()
        for t in range(1,10):
            sc.Increment(1, t)
        self.assertAlmostEqual(sc.S, 2.0, 2)

        for t in range(10,20):
            sc.Increment(1, t)
        self.assertAlmostEqual(sc.S, 2.0, 5)
        
    def test_Series24(self):
        sc = calc.ScoreCalc(tHalf=24)
        
        for t in range(1,20):
            sc.Increment(1, t*24)
        self.assertAlmostEqual(sc.S, 2.0, 5)
        
    def test_Zero(self):
        sc = calc.ScoreCalc(value=0)
        sLog = sc.LogS
        sc.Increment(0)
        self.assertEqual(sc.LogS, sLog)
        sc.Increment(0, 1)
        self.assertEqual(sc.LogS, sLog)
        

if __name__ == '__main__':
    unittest.main()