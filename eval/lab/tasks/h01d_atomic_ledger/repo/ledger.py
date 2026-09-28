import sqlite3
class Ledger:
 def __init__(self,path=":memory:"):
  self.db=sqlite3.connect(path)
  self.db.executescript("CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,balance INT NOT NULL); CREATE TABLE IF NOT EXISTS ops(key TEXT PRIMARY KEY,src TEXT,dst TEXT,amount INT);")
 def transfer(self,key,src,dst,amount):
  with self.db:
   self.db.execute("UPDATE accounts SET balance=balance-? WHERE id=?",(amount,src))
   self.db.execute("UPDATE accounts SET balance=balance+? WHERE id=?",(amount,dst))
  return True
