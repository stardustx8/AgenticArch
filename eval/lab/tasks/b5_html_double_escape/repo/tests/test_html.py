import unittest

from render import render_item, render_link, render_list, render_title


class HtmlTests(unittest.TestCase):
    def test_title_plain(self):
        self.assertEqual(render_title('Hello'), '<h1>Hello</h1>')

    def test_title_ampersand(self):
        self.assertEqual(render_title('Tom & Jerry'), '<h1>Tom &amp; Jerry</h1>')

    def test_item_escapes(self):
        self.assertEqual(render_item('a<b & c'), '<li>a&lt;b &amp; c</li>')

    def test_list(self):
        self.assertEqual(render_list(['x', 'y']), '<ul><li>x</li><li>y</li></ul>')

    def test_link(self):
        self.assertEqual(render_link('/search?q=1&page=2', 'Next'),
                         '<a href="/search?q=1&amp;page=2">Next</a>')


if __name__ == '__main__':
    unittest.main()
