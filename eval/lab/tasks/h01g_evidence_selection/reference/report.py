def report(records):
 groups={}
 for r in records:
  if r["status"]=="approved":groups.setdefault(r["product"],[]).append(r)
 out=[]
 for product,rows in sorted(groups.items()):
  rev=max(r["revision"] for r in rows);top=[r for r in rows if r["revision"]==rev]
  if any(r["value"]!=top[0]["value"] for r in top):raise ValueError("conflicting sources")
  r=min(top,key=lambda r:r["id"]);out.append(dict(product=product,value=r["value"],source=r["id"]))
 return out
