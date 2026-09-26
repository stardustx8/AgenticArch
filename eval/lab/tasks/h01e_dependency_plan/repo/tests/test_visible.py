import unittest
from planner import plan
class Test(unittest.TestCase):
 def test_empty_edges(self): self.assertEqual(plan({"b":[],"a":[]}),["a","b"])
