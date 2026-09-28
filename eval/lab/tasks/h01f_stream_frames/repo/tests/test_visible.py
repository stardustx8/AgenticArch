import unittest
from frames import Decoder
class Test(unittest.TestCase):
 def test_single(self): self.assertEqual(Decoder().feed(b"\x00\x00\x00\x03abc"),[b"abc"])
