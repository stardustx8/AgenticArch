def report(records):
 return [{"product":r["product"],"value":r["value"],"source":r["id"]} for r in records]
