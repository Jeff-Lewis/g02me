sChars64 = '-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz'

class StringKey(object):
    def __init__(self, sChars=sChars64, ratio=0.5):
        self.aChars = [ch for ch in sChars]
        self.aChars.sort()
        self.base = len(self.aChars)
        self.ratio = ratio
        self.iMid = int(ratio * self.base)
        assert self.iMid < self.base

        assert self.base >= 2
        self.mpVal = {}
        for i in range(self.base):
            self.mpVal[self.aChars[i]] = i
        
    def Tween(self, s1, s2):
        """
        Returns an alphabetic key between the given bracket strings.  Keys are interpreted
        as fractional digits chosen the the available characters.
        
        Empty strings passed for s1 or s2 denote the min and max strings, respectively.
        
        Note: s2 may not be all "0" characters (as no string can be created lower)
        """
        # Strip common prefix, and pad short string to equal longer one
        c1 = len(s1)
        c2 = len(s2)
        for i in range(c2-c1): s1 = s1 + self.aChars[0]
        for i in range(c1-c2): s2 = s2 + self.aChars[0]
        
        c = len(s1)
        
        iPre = 0
        for iPre in range(c):
            if s1[iPre] != s2[iPre]:
                break

        v1 = v2 = 0
        if c2 == 0:
            v2 = 1
        i = iPre
        for i in range(iPre, c):
            v1 = self.base * v1 + self.mpVal[s1[i]]
            v2 = self.base * v2 + self.mpVal[s2[i]]
            if v2 - v1 >= 2:
                return s1[:i] + self._MidChar(s1[i], v2-v1)
        
        return s1[:c] + self.aChars[self.iMid]
    
    def _MidChar(self, ch1, dch):
        i1 = self.mpVal[ch1]
        assert dch >= 2
        
        iMid = i1 + int(self.ratio * dch)
        if iMid == i1:
            iMid = i1 + 1
            
        return self.aChars[iMid]

import unittest

class TestStringKeys(unittest.TestCase):
    def test_chars(self):
        self.assertEqual(len(sChars64), 64)
        iLast = 0
        for ch in sChars64:
            self.assert_(ord(ch) > iLast)
            iLast = ord(ch)
            
    def test_basic(self):
        self.sk = StringKey("ABC")
        self.PatternTest([
            ['', '', 'B'],
            ['', 'B', 'AB'],
            ['A', 'C', 'B'],
            ['A', '', 'B'],
            ['A', 'B', 'AB'],
            ['C', '', 'CB'],
            ['ABBB', 'C', 'B'],
            ['CCBC', '', 'CCC'],
            ['ACCC', 'B', 'ACCCB']
            ])
        
    def test_normal(self):
        self.sk = StringKey()
        self.PatternTest([
            ['', '', 'V'],
            ['V', '', 'k'],
            ['k', '', 's'],
            ['s', '', 'w'],
            ['w', '', 'y'],
            ['y', '', 'z'],
            ['z', '', 'zV'],
            ])
        
    def test_skew(self):
        self.sk = StringKey(ratio=0.1)
        sLink = "5AFJNRUX_bdfhijklmnopqrstuvwxyz"
        for i in range(len(sLink)-1):
            self.assertEqual
        self.assertEqual(self.RangeTest(sLink[i], ''), sLink[i+1])
       
    def PatternTest(self, aTests):
        for t in aTests:
            self.assertEqual(self.RangeTest(t[0], t[1]), t[2])
               
    def RangeTest(self, s1, s2):
        key = self.sk.Tween(s1, s2)
        self.assert_(s1 < key)
        if s2 != '':
            self.assert_(key < s2)
        return key

if __name__ == '__main__':
    sk = StringKey(ratio=0.1)
    ch = ''
    for i in range(100):
        ch = sk.Tween(ch, '')
        print ch
    unittest.main()

