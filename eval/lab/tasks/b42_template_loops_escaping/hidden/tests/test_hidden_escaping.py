import unittest

from tmpl import Environment, Markup, escape, render

TRICKY = 'say "hi" & ' + "it's <now>"
ESCAPED = 'say &quot;hi&quot; &amp; it&#39;s &lt;now&gt;'


class HiddenQuoteEscapingTest(unittest.TestCase):
    def test_autoescaped_output_in_attribute(self):
        out = render('<a title="{{ t }}">', t=TRICKY)
        self.assertEqual(out, '<a title="' + ESCAPED + '">')

    def test_escape_function(self):
        self.assertEqual(escape(TRICKY), ESCAPED)
        self.assertIsInstance(escape(TRICKY), Markup)

    def test_escape_filter_with_autoescape_off(self):
        env = Environment(autoescape=False)
        self.assertEqual(env.from_string('{{ t|escape }}').render(t=TRICKY), ESCAPED)
        self.assertEqual(env.from_string('{{ t|e }}').render(t=TRICKY), ESCAPED)

    def test_escape_filter_forces_escaping_of_markup(self):
        self.assertEqual(render('{{ t|safe|e }}', t=TRICKY), ESCAPED)
        self.assertEqual(render('{{ t|e }}', t=Markup(TRICKY)), ESCAPED)

    def test_safe_still_skips_escaping(self):
        self.assertEqual(render('{{ t|safe }}', t=TRICKY), TRICKY)

    def test_ampersand_is_escaped_exactly_once(self):
        self.assertEqual(render('{{ t }}', t='&quot; &#39;'), '&amp;quot; &amp;#39;')
        self.assertEqual(render('{{ t|e }}', t='"'), '&quot;')

    def test_escaped_values_inside_loops(self):
        out = render('{% for t in ts %}[{{ t }}]{% endfor %}', ts=['"', "'"])
        self.assertEqual(out, '[&quot;][&#39;]')
