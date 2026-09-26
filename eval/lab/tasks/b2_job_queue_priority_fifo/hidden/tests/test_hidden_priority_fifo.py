import unittest

from taskq import DuplicateJob, Job, JobQueue, QueueEmpty, drain


def make(job_id, priority=0, **payload):
    return Job(job_id, dict(payload), priority)


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        self.q = JobQueue()

    def submit_all(self, specs):
        for job_id, priority in specs:
            self.q.submit(make(job_id, priority))

    def pop_all(self):
        jobs = []
        while True:
            try:
                jobs.append(self.q.pop())
            except QueueEmpty:
                return jobs

    def pop_all_ids(self):
        return [job.id for job in self.pop_all()]


class EqualPriorityOrderTests(QueueTestCase):
    def test_equal_priorities_pop_in_submission_order(self):
        ids = [f"job-{i}" for i in range(12)]
        self.submit_all((job_id, 3) for job_id in ids)
        self.assertEqual(len(self.q), 12)
        self.assertEqual(self.pop_all_ids(), ids)

    def test_ties_are_fifo_within_each_priority(self):
        self.submit_all([("a", 2), ("b", 1), ("c", 2), ("d", 1), ("e", 0), ("f", 2), ("g", 1)])
        expected = ["e", "b", "d", "g", "a", "c", "f"]
        self.assertEqual(self.q.pending_ids(), expected)
        self.assertEqual(self.pop_all_ids(), expected)

    def test_peek_returns_earliest_submitted_among_ties(self):
        self.submit_all([("first", 1), ("second", 1), ("third", 1)])
        self.assertEqual(self.q.peek().id, "first")
        self.assertEqual(self.q.pop().id, "first")
        self.assertEqual(self.q.peek().id, "second")

    def test_interleaved_submit_and_pop_keep_fifo(self):
        self.submit_all([("a", 1), ("b", 1)])
        self.assertEqual(self.q.pop().id, "a")
        self.submit_all([("c", 1), ("d", 0), ("e", 1)])
        self.assertEqual(self.pop_all_ids(), ["d", "b", "c", "e"])

    def test_popped_id_can_be_resubmitted(self):
        self.q.submit(make("a", 0, v=1))
        self.q.submit(make("b", 0))
        self.assertEqual(self.q.pop().id, "a")
        self.q.submit(make("a", 0, v=2))
        jobs = self.pop_all()
        self.assertEqual([job.id for job in jobs], ["b", "a"])
        self.assertEqual(jobs[1].payload, {"v": 2})

    def test_duplicate_pending_id_still_rejected_among_ties(self):
        self.submit_all([("a", 0), ("b", 0)])
        with self.assertRaises(DuplicateJob):
            self.q.submit(make("a", 0))
        with self.assertRaises(DuplicateJob):
            self.q.submit(make("b", 5))
        self.assertEqual(len(self.q), 2)
        self.assertEqual(self.pop_all_ids(), ["a", "b"])


class CancelTests(QueueTestCase):
    def test_cancel_pending_job(self):
        self.submit_all([("a", 0), ("b", 0), ("c", 0)])
        self.assertIs(self.q.cancel("b"), True)
        self.assertEqual(len(self.q), 2)
        self.assertEqual(self.pop_all_ids(), ["a", "c"])

    def test_cancel_returns_false_when_nothing_pending(self):
        self.assertIs(self.q.cancel("ghost"), False)
        self.submit_all([("a", 0), ("b", 0)])
        self.assertIs(self.q.cancel("ghost"), False)
        self.assertIs(self.q.cancel("a"), True)
        self.assertIs(self.q.cancel("a"), False)
        self.assertEqual(self.q.pop().id, "b")
        self.assertIs(self.q.cancel("b"), False)
        self.assertEqual(len(self.q), 0)

    def test_peek_skips_cancelled_head(self):
        self.submit_all([("a", 0), ("b", 0), ("c", 1)])
        self.q.cancel("a")
        self.assertEqual(self.q.peek().id, "b")
        self.q.cancel("b")
        self.assertEqual(self.q.peek().id, "c")
        self.assertEqual(self.q.pop().id, "c")

    def test_only_cancelled_jobs_left_behaves_as_empty(self):
        self.submit_all([("a", 0), ("b", 0)])
        self.q.cancel("a")
        self.q.cancel("b")
        self.assertEqual(len(self.q), 0)
        self.assertEqual(self.q.pending_ids(), [])
        with self.assertRaises(QueueEmpty):
            self.q.peek()
        with self.assertRaises(QueueEmpty):
            self.q.pop()

    def test_pending_ids_exclude_cancelled(self):
        self.submit_all([("a", 1), ("b", 0), ("c", 1), ("d", 0)])
        self.q.cancel("c")
        self.q.cancel("b")
        self.assertEqual(self.q.pending_ids(), ["d", "a"])
        self.assertEqual(len(self.q), 2)

    def test_cancelled_id_resubmitted_goes_to_back_of_its_priority(self):
        self.q.submit(make("a", 0, v=1))
        self.submit_all([("b", 0), ("c", 0)])
        self.assertTrue(self.q.cancel("a"))
        self.q.submit(make("a", 0, v=2))
        self.assertEqual(len(self.q), 3)
        with self.assertRaises(DuplicateJob):
            self.q.submit(make("a", 0, v=3))
        self.assertEqual(self.q.pending_ids(), ["b", "c", "a"])
        jobs = self.pop_all()
        self.assertEqual([job.id for job in jobs], ["b", "c", "a"])
        self.assertEqual(jobs[-1].payload, {"v": 2})

    def test_resubmitted_job_uses_its_new_priority(self):
        self.q.submit(make("a", 5, v=1))
        self.q.submit(make("b", 1))
        self.q.cancel("a")
        self.q.submit(make("a", 0, v=2))
        jobs = self.pop_all()
        self.assertEqual([job.id for job in jobs], ["a", "b"])
        self.assertEqual(jobs[0].payload, {"v": 2})

    def test_drain_skips_cancelled_and_keeps_fifo(self):
        self.submit_all((f"job-{i}", i % 2) for i in range(6))
        self.q.cancel("job-2")
        self.q.cancel("job-3")
        seen = []
        processed = drain(self.q, seen.append)
        expected = ["job-0", "job-4", "job-1", "job-5"]
        self.assertEqual(processed, expected)
        self.assertEqual([job.id for job in seen], expected)
        self.assertEqual(len(self.q), 0)

    def test_drain_limit_counts_only_real_jobs(self):
        self.submit_all([("a", 0), ("b", 0), ("c", 0), ("d", 0)])
        self.q.cancel("a")
        self.q.cancel("b")
        self.assertEqual(drain(self.q, lambda job: None, limit=1), ["c"])
        self.assertEqual(self.q.pending_ids(), ["d"])


if __name__ == "__main__":
    unittest.main()
