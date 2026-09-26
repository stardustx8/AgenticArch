from pathlib import Path
def latest(db):
 return db.execute(Path(__file__).with_name("latest.sql").read_text()).fetchall()
