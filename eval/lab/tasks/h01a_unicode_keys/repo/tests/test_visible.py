import unittest
from keys import canonical_key
class Test(unittest.TestCase):
 def test_ascii(self): self.assertEqual(canonical_key(" Hello "),"hello")
