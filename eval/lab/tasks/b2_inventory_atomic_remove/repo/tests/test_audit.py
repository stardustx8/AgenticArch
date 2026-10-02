import unittest

from stockroom.audit import AuditEntry, AuditLog


class AuditLogTests(unittest.TestCase):
    def test_for_sku_and_net_change(self):
        log = AuditLog()
        log.record("add", "APPLE", 5)
        log.record("add", "PEAR", 2)
        log.record("remove", "APPLE", 3)
        self.assertEqual(
            log.for_sku("APPLE"),
            [AuditEntry("add", "APPLE", 5), AuditEntry("remove", "APPLE", 3)],
        )
        self.assertEqual(log.net_change("APPLE"), 2)
        self.assertEqual(log.net_change("KIWI"), 0)

    def test_entries_is_a_copy_and_actions_are_checked(self):
        log = AuditLog()
        log.record("add", "APPLE", 1)
        log.entries().clear()
        self.assertEqual(len(log), 1)
        with self.assertRaises(ValueError):
            log.record("steal", "APPLE", 1)
        self.assertEqual(len(log), 1)


if __name__ == "__main__":
    unittest.main()
