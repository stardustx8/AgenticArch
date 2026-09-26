class Decoder:
 def __init__(self):self.reset()
 def reset(self):self.buffer=bytearray();self.failed=False
 def feed(self,data):
  if self.failed:raise ValueError("decoder failed")
  self.buffer.extend(data);out=[]
  while len(self.buffer)>=4:
   n=int.from_bytes(self.buffer[:4],"big")
   if n>1024:
    self.buffer.clear();self.failed=True;raise ValueError("oversize")
   if len(self.buffer)<4+n:break
   out.append(bytes(self.buffer[4:4+n]));del self.buffer[:4+n]
  return out
