from dataclasses import dataclass


@dataclass
class Reservation:
    order_id: str
    sku: str
    warehouse: str
    qty: int


class ReservationBook:
    def __init__(self):
        self._items = []

    def add(self, order_id, sku, warehouse, qty):
        reservation = Reservation(order_id, sku, warehouse, qty)
        self._items.append(reservation)
        return reservation

    def for_order(self, order_id):
        return [item for item in self._items if item.order_id == order_id]

    def remove_order(self, order_id):
        removed = self.for_order(order_id)
        self._items = [item for item in self._items if item.order_id != order_id]
        return removed

    def totals_for(self, order_id):
        '''{(sku, warehouse): qty} reserved for an order.'''
        totals = {}
        for item in self.for_order(order_id):
            key = (item.sku, item.warehouse)
            totals[key] = totals.get(key, 0) + item.qty
        return totals
