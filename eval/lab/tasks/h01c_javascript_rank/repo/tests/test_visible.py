import subprocess,unittest
class Test(unittest.TestCase):
 def test_order(self):
  p=subprocess.run(["node","-e","const a=require('./rank').rank([{priority:2},{priority:1}]); if(a[0].priority!==1) process.exit(1)"],capture_output=True)
  self.assertEqual(p.returncode,0)
