import unittest,copy
from report import report
class Hidden(unittest.TestCase):
 def test_sources(self):
  rows=[dict(product="a",value=v,id=i,revision=r,status=s,private="omit") for v,i,r,s in [(1,"old",1,"approved"),(3,"pending",3,"draft"),(2,"z",2,"approved"),(2,"b",2,"approved")]]
  old=copy.deepcopy(rows);self.assertEqual(report(rows),[{"product":"a","value":2,"source":"b"}]);self.assertEqual(rows,old)
  self.assertEqual(report([]),[])
  rows.append(dict(product="a",value=4,id="conflict",revision=2,status="approved"))
  with self.assertRaises(ValueError):report(rows)
