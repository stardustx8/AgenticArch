import subprocess,unittest
class Hidden(unittest.TestCase):
 def test_contract(self):
  code="const {rank}=require('./rank'); const a=[{id:0},{id:1,priority:2},{id:2,priority:-1},{id:3,priority:2},{id:4,priority:Infinity},{id:5,priority:'0'}];const r=rank(a);if(r===a||a[0].id!==0||r.map(x=>x.id).join()!='2,1,3,0,4,5')throw Error('contract');if(rank([]).length)throw Error('empty');"
  p=subprocess.run(["node","-e",code],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr)
