import unittest

from throttle import BucketRegistry, FakeClock


class BucketRegistryTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.registry = BucketRegistry(2, 1.0, clock=self.clock)

    def test_same_client_gets_same_bucket(self):
        self.assertIs(self.registry.get("alice"), self.registry.get("alice"))
        self.assertEqual(len(self.registry), 1)
        self.assertNotIn("bob", self.registry)

    def test_clients_are_independent(self):
        self.assertTrue(self.registry.try_acquire("alice", 2))
        self.assertFalse(self.registry.try_acquire("alice"))
        self.assertTrue(self.registry.try_acquire("bob"))

    def test_forget_resets_client(self):
        self.registry.try_acquire("alice", 2)
        self.registry.forget("alice")
        self.assertNotIn("alice", self.registry)
        self.assertTrue(self.registry.try_acquire("alice", 2))


if __name__ == "__main__":
    unittest.main()
