import unittest

from taskq import DuplicateJob, Job, JobQueue, QueueEmpty


class JobQueueTests(unittest.TestCase):
    def setUp(self):
        self.q = JobQueue()

    def test_lowest_priority_number_pops_first(self):
        for job_id, priority in [("report", 5), ("email", 1), ("resize", 3)]:
            self.q.submit(Job(job_id, {}, priority))
        self.assertEqual([self.q.pop().id for _ in range(3)], ["email", "resize", "report"])
        self.assertEqual(len(self.q), 0)

    def test_duplicate_pending_id_rejected(self):
        self.q.submit(Job("sync", {"n": 1}, 1))
        with self.assertRaises(DuplicateJob):
            self.q.submit(Job("sync", {"n": 2}, 2))
        self.assertEqual(len(self.q), 1)
        self.assertEqual(self.q.pop().payload, {"n": 1})

    def test_empty_queue_raises(self):
        with self.assertRaises(QueueEmpty):
            self.q.pop()
        with self.assertRaises(QueueEmpty):
            self.q.peek()

    def test_peek_does_not_remove(self):
        self.q.submit(Job("a", {}, 2))
        self.q.submit(Job("b", {}, 1))
        self.assertEqual(self.q.peek().id, "b")
        self.assertEqual(len(self.q), 2)
        self.assertEqual(self.q.pop().id, "b")

    def test_pending_ids_in_pop_order(self):
        for job_id, priority in [("c", 3), ("a", 1), ("b", 2)]:
            self.q.submit(Job(job_id, {}, priority))
        self.assertEqual(self.q.pending_ids(), ["a", "b", "c"])
        self.assertIn("a", self.q)
        self.q.pop()
        self.assertEqual(self.q.pending_ids(), ["b", "c"])
        self.assertNotIn("a", self.q)


if __name__ == "__main__":
    unittest.main()
