import unittest
from planner import plan
class Hidden(unittest.TestCase):
 def test_dag(self):
  g={"a":["z","z"],"b":[],"z":[]}
  self.assertEqual(plan(g),["b","z","a"]);self.assertEqual(g["a"],["z","z"])
  self.assertEqual(plan({}),[])
 def test_invalid(self):
  for g in ({"a":["x"]},{"a":["a"]},{"a":["b"],"b":["a"]}):
   with self.assertRaises(ValueError): plan(g)
