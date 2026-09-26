import unittest

from tagging import TagIndex


class HiddenCaseInsensitiveLookupTests(unittest.TestCase):
    def setUp(self):
        self.index = TagIndex()
        self.index.add('post-1', 'Python', 'testing')
        self.index.add('post-2', 'python', ' Web ')
        self.index.add('post-3', 'web')

    def test_find_ignores_case_and_whitespace(self):
        self.assertEqual(self.index.find('Python'), ['post-1', 'post-2'])
        self.assertEqual(self.index.find('  WEB '), ['post-2', 'post-3'])

    def test_count_ignores_case(self):
        self.assertEqual(self.index.count('PYTHON'), 2)
        self.assertEqual(self.index.count(' Testing'), 1)

    def test_remove_tag_ignores_case(self):
        self.assertTrue(self.index.remove_tag('post-1', 'PYTHON'))
        self.assertEqual(self.index.find('python'), ['post-2'])
        self.assertEqual(self.index.tags_of('post-1'), ['testing'])
        self.assertFalse(self.index.remove_tag('post-1', 'Python'))

    def test_remove_last_item_drops_tag(self):
        self.assertTrue(self.index.remove_tag('post-1', ' Testing '))
        self.assertEqual(self.index.count('testing'), 0)
        self.assertEqual(self.index.popular(5), [('python', 2), ('web', 2)])
