import unittest

from taskq import Job, JobQueue, drain


class DrainTests(unittest.TestCase):
    def setUp(self):
        self.q = JobQueue()
        for job_id, priority in [("low", 9), ("high", 0), ("mid", 4)]:
            self.q.submit(Job(job_id, {"name": job_id}, priority))

    def test_drain_processes_everything_in_order(self):
        seen = []
        processed = drain(self.q, lambda job: seen.append(job.payload["name"]))
        self.assertEqual(processed, ["high", "mid", "low"])
        self.assertEqual(seen, processed)
        self.assertEqual(len(self.q), 0)

    def test_drain_respects_limit(self):
        self.assertEqual(drain(self.q, lambda job: None, limit=2), ["high", "mid"])
        self.assertEqual(self.q.pending_ids(), ["low"])

    def test_negative_limit_rejected(self):
        with self.assertRaises(ValueError):
            drain(self.q, lambda job: None, limit=-1)
        self.assertEqual(len(self.q), 3)


if __name__ == "__main__":
    unittest.main()
