import unittest
from intervals import union
class Hidden(unittest.TestCase):
 def test_contract(self):
  a=[(1,3),(2,4),(4,5),(9,9)];self.assertEqual(union(a),[(1,4),(4,5)])
  self.assertEqual(union(a,True),[(1,5)]);self.assertEqual(len(a),4)
  self.assertEqual(union([]),[])
  with self.assertRaises(ValueError):union([(5,2)])
