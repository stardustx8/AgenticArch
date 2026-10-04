import unittest

from throttle.window import SlidingLog


class SlidingLogTests(unittest.TestCase):
    def test_record_and_total(self):
        log = SlidingLog()
        log.record(0.0, 2)
        log.record(1.0, 3)
        self.assertEqual(log.total(), 5)
        self.assertEqual(len(log), 2)
        self.assertEqual(log.oldest(), 0.0)

    def test_prune_drops_old_events(self):
        log = SlidingLog()
        log.record(0.0, 1)
        log.record(4.0, 2)
        log.record(9.0, 3)
        log.prune(12.0, 10.0)
        self.assertEqual(log.entries(), [(4.0, 2), (9.0, 3)])
        self.assertEqual(log.total(), 5)

    def test_prune_keeps_recent_events(self):
        log = SlidingLog()
        log.record(5.0, 1)
        log.prune(9.0, 10.0)
        self.assertEqual(len(log), 1)

    def test_out_of_order_record_rejected(self):
        log = SlidingLog()
        log.record(5.0, 1)
        with self.assertRaises(ValueError):
            log.record(4.0, 1)

    def test_empty_log(self):
        log = SlidingLog()
        self.assertIsNone(log.oldest())
        self.assertEqual(log.total(), 0)
