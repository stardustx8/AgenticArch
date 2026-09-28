import unittest
from ledger import Ledger
class Test(unittest.TestCase):
 def test_move(self):
  x=Ledger();self.addCleanup(x.db.close)
  x.db.executemany("INSERT INTO accounts VALUES(?,?)",[("a",10),("b",0)]);x.db.commit()
  self.assertTrue(x.transfer("one","a","b",3))
  self.assertEqual(x.db.execute("SELECT balance FROM accounts ORDER BY id").fetchall(),[(7,),(3,)])
