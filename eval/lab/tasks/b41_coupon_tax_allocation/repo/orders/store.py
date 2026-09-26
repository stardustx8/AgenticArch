import json
import os

from .models import OrderRecord


class DuplicateOrder(ValueError):
    pass


class OrderNotFound(KeyError):
    pass


class OrderStore:
    '''All orders in a single JSON file: {'orders': [record, ...]}.'''

    def __init__(self, path):
        self.path = path

    def _read(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding='utf-8') as fh:
            raw = json.load(fh)
        records = []
        for item in raw.get('orders', []):
            try:
                records.append(OrderRecord.from_dict(item))
            except (KeyError, TypeError, ValueError, ArithmeticError):
                # entries half-written by crashed runs are ignored
                continue
        return records

    def _write(self, records):
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'orders': [record.to_dict() for record in records]}, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def save(self, record):
        records = self._read()
        if any(existing.order_id == record.order_id for existing in records):
            raise DuplicateOrder(record.order_id)
        records.append(record)
        self._write(records)

    def load(self, order_id):
        for record in self._read():
            if record.order_id == order_id:
                return record
        raise OrderNotFound(order_id)

    def list_ids(self):
        return [record.order_id for record in self._read()]
