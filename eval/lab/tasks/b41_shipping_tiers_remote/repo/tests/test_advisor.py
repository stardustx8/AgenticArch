import unittest

from shipping.advisor import weight_headroom


class AdvisorTest(unittest.TestCase):
    def test_no_headroom_past_top_tier(self):
        self.assertIsNone(weight_headroom(25000))
        self.assertIsNone(weight_headroom(30000, 'express'))


if __name__ == '__main__':
    unittest.main()
