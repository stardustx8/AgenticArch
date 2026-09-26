import unittest,tempfile
from ledger import Ledger
class Hidden(unittest.TestCase):
 def test_contract(self):
  with tempfile.TemporaryDirectory() as d:
   x=Ledger(d+"/db"); self.addCleanup(x.db.close)
   x.db.executemany("INSERT INTO accounts VALUES(?,?)",[("a",10),("b",0)]);x.db.commit()
   self.assertTrue(x.transfer("one","a","b",3))
   self.assertFalse(x.transfer("one","a","b",3))
   for args in [("one","a","b",4),("bad","a","b",99),("bad","a","c",2),("bad","a","a",2),("bad","a","b",True),("bad","a","b",-1)]:
    with self.assertRaises(ValueError): x.transfer(*args)
   self.assertEqual(x.db.execute("SELECT balance FROM accounts ORDER BY id").fetchall(),[(7,),(3,)])
   self.assertEqual(x.db.execute("SELECT COUNT(*) FROM ops").fetchone()[0],1)
   y=Ledger(d+"/db");self.addCleanup(y.db.close)
   self.assertFalse(y.transfer("one","a","b",3))
