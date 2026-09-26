import sqlite3,unittest
from query import latest
class Hidden(unittest.TestCase):
 def test_latest(self):
  with sqlite3.connect(":memory:") as db:
   db.execute("CREATE TABLE events(customer_id TEXT,event_id INT,amount INT,happened_at INT,status TEXT)")
   db.executemany("INSERT INTO events VALUES(?,?,?,?,?)",[("a",1,5,1,"completed"),("a",2,7,2,"completed"),("a",3,9,2,"completed"),("a",4,99,3,"pending"),("b",1,8,3,"completed"),("c",1,4,1,"pending")])
   self.assertEqual(latest(db),[("a",3,9),("b",1,8)])
