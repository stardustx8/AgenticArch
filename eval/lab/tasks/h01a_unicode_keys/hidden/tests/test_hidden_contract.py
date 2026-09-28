import unittest
from keys import canonical_key
class Hidden(unittest.TestCase):
 def test_unicode(self):
  for a,b in [("Straße","strasse"),(" e\u0301 ","é"),("A\u2003B\tC","a b c"),(" ",""),("CAFÉ!","café!")]:
   self.assertEqual(canonical_key(a),b)
