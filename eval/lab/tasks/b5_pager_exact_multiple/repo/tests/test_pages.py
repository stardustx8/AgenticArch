import unittest

from pager import has_next, has_prev, last_page_size, page_count, page_numbers, page_slice


class PagerTests(unittest.TestCase):
    def test_page_count(self):
        self.assertEqual(page_count(11, 5), 3)
        self.assertEqual(page_count(4, 5), 1)

    def test_page_count_rejects_bad_size(self):
        with self.assertRaises(ValueError):
            page_count(10, 0)

    def test_page_slice(self):
        items = list(range(12))
        self.assertEqual(page_slice(items, 1, 5), [0, 1, 2, 3, 4])
        self.assertEqual(page_slice(items, 3, 5), [10, 11])

    def test_navigation(self):
        self.assertFalse(has_prev(1))
        self.assertTrue(has_prev(2))
        self.assertTrue(has_next(1, 11, 5))
        self.assertTrue(has_next(2, 11, 5))
        self.assertFalse(has_next(3, 11, 5))

    def test_last_page_size(self):
        self.assertEqual(last_page_size(12, 5), 2)

    def test_page_numbers(self):
        self.assertEqual(page_numbers(11, 5), [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
