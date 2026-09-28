import sqlite3
class Ledger:
 def __init__(self,path=":memory:"):
  self.db=sqlite3.connect(path)
  self.db.executescript("CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,balance INT NOT NULL); CREATE TABLE IF NOT EXISTS ops(key TEXT PRIMARY KEY,src TEXT,dst TEXT,amount INT);")
 def transfer(self,key,src,dst,amount):
  if type(amount) is not int or amount<=0 or src==dst: raise ValueError("invalid transfer")
  try:
   self.db.execute("BEGIN IMMEDIATE")
   old=self.db.execute("SELECT src,dst,amount FROM ops WHERE key=?",(key,)).fetchone()
   if old is not None:
    if old!=(src,dst,amount): raise ValueError("idempotency conflict")
    self.db.rollback();return False
   source=self.db.execute("SELECT balance FROM accounts WHERE id=?",(src,)).fetchone()
   target=self.db.execute("SELECT balance FROM accounts WHERE id=?",(dst,)).fetchone()
   if source is None or target is None or source[0]<amount: raise ValueError("account or funds")
   self.db.execute("UPDATE accounts SET balance=balance-? WHERE id=?",(amount,src))
   self.db.execute("UPDATE accounts SET balance=balance+? WHERE id=?",(amount,dst))
   self.db.execute("INSERT INTO ops VALUES(?,?,?,?)",(key,src,dst,amount))
   self.db.commit();return True
  except Exception:
   self.db.rollback();raise
