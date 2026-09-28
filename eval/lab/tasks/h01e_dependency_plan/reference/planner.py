import heapq
def plan(graph):
 deps={k:set(v) for k,v in graph.items()}
 if any(d not in deps for ds in deps.values() for d in ds):raise ValueError("missing dependency")
 reverse={k:set() for k in deps}
 for k,ds in deps.items():
  for d in ds:reverse[d].add(k)
 ready=[k for k,ds in deps.items() if not ds];heapq.heapify(ready);out=[]
 while ready:
  k=heapq.heappop(ready);out.append(k)
  for next in reverse[k]:
   deps[next].remove(k)
   if not deps[next]:heapq.heappush(ready,next)
 if len(out)!=len(deps):raise ValueError("cycle")
 return out
