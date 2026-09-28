import unittest
from intervals import union
class Test(unittest.TestCase):
 def test_disjoint(self):self.assertEqual(union([(3,4),(1,2)]),[(1,2),(3,4)])
