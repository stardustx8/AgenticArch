def union(intervals,merge_touching=False):
 data=[]
 for a,b in intervals:
  if a>b:raise ValueError("reversed interval")
  if a<b:data.append((a,b))
 out=[]
 for a,b in sorted(data):
  if out and (a<out[-1][1] or (merge_touching and a==out[-1][1])):
   out[-1]=(out[-1][0],max(b,out[-1][1]))
  else:out.append((a,b))
 return out
