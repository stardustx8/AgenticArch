import unittest

from pager import has_next, last_page_size, page_count, page_numbers, page_slice


class HiddenExactMultipleTests(unittest.TestCase):
    def test_page_count_exact_multiple(self):
        self.assertEqual(page_count(10, 5), 2)
        self.assertEqual(page_count(5, 5), 1)
        self.assertEqual(page_count(100, 25), 4)
        self.assertEqual(page_count(11, 5), 3)
        self.assertEqual(page_count(1, 5), 1)

    def test_page_numbers_exact_multiple(self):
        self.assertEqual(page_numbers(10, 5), [1, 2])

    def test_has_next_exact_multiple(self):
        self.assertTrue(has_next(1, 10, 5))
        self.assertFalse(has_next(2, 10, 5))
        self.assertFalse(has_next(1, 5, 5))
        self.assertFalse(has_next(4, 100, 25))

    def test_has_next_agrees_with_page_count(self):
        for total in range(1, 40):
            for per_page in (1, 3, 5, 10):
                pages = page_count(total, per_page)
                for page in range(1, pages + 1):
                    self.assertEqual(has_next(page, total, per_page), page < pages,
                                     (page, total, per_page))

    def test_last_page_size_exact_multiple(self):
        self.assertEqual(last_page_size(10, 5), 5)
        self.assertEqual(last_page_size(12, 5), 2)
        self.assertEqual(last_page_size(3, 5), 3)

    def test_last_page_matches_slice(self):
        items = list(range(20))
        for per_page in (1, 4, 5, 7):
            pages = page_count(len(items), per_page)
            self.assertEqual(len(page_slice(items, pages, per_page)),
                             last_page_size(len(items), per_page))
