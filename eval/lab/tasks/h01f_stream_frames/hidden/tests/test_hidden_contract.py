import unittest
from frames import Decoder
class Hidden(unittest.TestCase):
 def test_every_split(self):
  wire=b"\x00\x00\x00\x03abc\x00\x00\x00\x00\x00\x00\x00\x02de"
  for split in range(len(wire)+1):
   d=Decoder();self.assertEqual(d.feed(wire[:split])+d.feed(wire[split:]),[b"abc",b"",b"de"])
 def test_failed(self):
  d=Decoder()
  with self.assertRaises(ValueError): d.feed((1025).to_bytes(4,"big"))
  with self.assertRaises(ValueError): d.feed(b"")
  d.reset();self.assertEqual(d.feed(b"\x00\x00\x00\x00"),[b""])
