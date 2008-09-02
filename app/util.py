import threading

s64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
def IntToS64(i):
    # Convert int to "base 64" string - not compatible with Base64 string standard
    s = []
    while i != 0:
        b = i % 64
        s = [s64[b]] + s
        i = i/64
    return ''.join(s)

def NormalizeUrl(url):
    return url.strip()

def TrimString(st):
    return st.strip()

# We save request info in a thread-global
local = threading.local()

import unittest

class TestIntToS64(unittest.TestCase):
    def test(self):
        i = 1
        for ch in s64[1:]:
            self.assertEqual(IntToS64(i), ch)
            i = i + 1
        self.assertEqual(IntToS64(64), "10")
        self.assertEqual(IntToS64(64*64+10), "10A")
        print 64 ** 5
        self.assertEqual(IntToS64(64 ** 5), "100000")
        
class TestNormalizeUrl(unittest.TestCase):
    def test(self):
        self.assertEqual(NormalizeUrl("http://hello"), "http://hello")
        self.assertEqual(NormalizeUrl("  http://hello  "), "http://hello")

if __name__ == '__main__':
  unittest.main()