import sqlite3,unittest
from query import latest
class Test(unittest.TestCase):
 def test_one(self):
  with sqlite3.connect(":memory:") as db:
   db.execute("CREATE TABLE events(customer_id TEXT,event_id INT,amount INT,happened_at INT,status TEXT)")
   db.execute("INSERT INTO events VALUES('a',1,5,1,'completed')")
   self.assertEqual(latest(db),[("a",1,5)])
