import unittest

from reports.fx import RateTable
from reports.loader import load_transactions
from reports.tax_export import export_csv, vat_lines

LINES = [
    'date,region,category,amount,currency',
    '2024-02-01,North,Food,12.34,USD',
    '2024-02-02,South,services,10.00,USD',
    '2024-02-03,South,misc,7.00,USD',
    '2024-02-04,West,books,20.00,EUR',
]


class TaxExportTest(unittest.TestCase):
    def setUp(self):
        self.rows = load_transactions(LINES)
        self.rates = RateTable('USD', {'EUR': '1.10'})

    def test_vat_lines(self):
        lines = vat_lines(self.rows, self.rates)
        self.assertEqual([(c, str(n), str(v)) for _, c, n, v in lines], [
            ('Food', '12.34', '1.23'),
            ('services', '10.00', '2.00'),
            ('misc', '7.00', '0.00'),
            ('books', '22.00', '1.10'),
        ])

    def test_export_csv(self):
        text = export_csv(self.rows[:2], self.rates)
        self.assertEqual(text, 'date,category,net,vat\n2024-02-01,Food,12.34,1.23\n2024-02-02,services,10.00,2.00\n')
