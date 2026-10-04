from .models import LineItem


def line_net(item: LineItem):
    return round(item.unit_price * item.quantity, 2)


def line_tax(item: LineItem):
    return round(line_net(item) * item.tax_rate, 2)


def invoice_totals(items):
    net = sum(line_net(i) for i in items)
    tax = sum(line_tax(i) for i in items)
    return {"net": round(net, 2), "tax": round(tax, 2), "gross": round(net + tax, 2)}
