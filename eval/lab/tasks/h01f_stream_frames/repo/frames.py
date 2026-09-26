class Decoder:
 def feed(self,data):
  return [data[4:]] if len(data)>=4 else []
 def reset(self):pass
