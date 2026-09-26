import unittest

from tagging import TagIndex


class TagIndexTests(unittest.TestCase):
    def setUp(self):
        self.index = TagIndex()
        self.index.add('post-1', 'Python', 'testing')
        self.index.add('post-2', 'python', ' Web ')
        self.index.add('post-3', 'web')

    def test_find(self):
        self.assertEqual(self.index.find('python'), ['post-1', 'post-2'])
        self.assertEqual(self.index.find('missing'), [])

    def test_find_all(self):
        self.assertEqual(self.index.find_all('PYTHON', 'Web'), ['post-2'])

    def test_tags_are_normalized(self):
        self.assertEqual(self.index.tags_of('post-2'), ['python', 'web'])

    def test_count(self):
        self.assertEqual(self.index.count('web'), 2)

    def test_remove_tag(self):
        self.assertTrue(self.index.remove_tag('post-3', 'web'))
        self.assertEqual(self.index.find('web'), ['post-2'])
        self.assertEqual(self.index.tags_of('post-3'), [])
        self.assertFalse(self.index.remove_tag('post-3', 'web'))

    def test_popular(self):
        self.assertEqual(self.index.popular(2), [('python', 2), ('web', 2)])


if __name__ == '__main__':
    unittest.main()
