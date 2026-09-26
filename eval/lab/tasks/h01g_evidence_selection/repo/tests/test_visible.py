import unittest
from report import report
class Test(unittest.TestCase):
 def test_one(self): self.assertEqual(report([dict(product="a",value=2,id="s",revision=1,status="approved")]),[{"product":"a","value":2,"source":"s"}])
