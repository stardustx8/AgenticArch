import unittest

from render import render_item, render_link, render_list, render_title


class HiddenEscapingTests(unittest.TestCase):
    def test_title_angle_brackets(self):
        self.assertEqual(render_title('a < b'), '<h1>a &lt; b</h1>')
        self.assertEqual(render_title('<script>'), '<h1>&lt;script&gt;</h1>')
        self.assertEqual(render_title('1 < 2 & 3 > 2'), '<h1>1 &lt; 2 &amp; 3 &gt; 2</h1>')

    def test_link_label_angle_brackets(self):
        self.assertEqual(render_link('/', 'x > y'), '<a href="/">x &gt; y</a>')
        self.assertEqual(render_link('/', 'a<b&c'), '<a href="/">a&lt;b&amp;c</a>')

    def test_link_href_quotes(self):
        self.assertEqual(render_link('/s?q="x"', 'find'),
                         '<a href="/s?q=&quot;x&quot;">find</a>')
        self.assertEqual(render_link('/s?a="1"&b=2', 'go'),
                         '<a href="/s?a=&quot;1&quot;&amp;b=2">go</a>')

    def test_literal_entities_are_escaped_once(self):
        self.assertEqual(render_title('&lt;'), '<h1>&amp;lt;</h1>')
        self.assertEqual(render_item('x < y'), '<li>x &lt; y</li>')
        self.assertEqual(render_list(['<a>']), '<ul><li>&lt;a&gt;</li></ul>')
