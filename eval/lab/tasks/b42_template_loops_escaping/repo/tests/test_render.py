import unittest

from tmpl import Environment, Markup, TemplateSyntaxError, UndefinedError, render
from tmpl.lexer import BLOCK, TEXT, VAR, tokenize


class User:
    def __init__(self, name, tags):
        self.name = name
        self.tags = tags


class LexerTest(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(
            tokenize('a{{ x }}b{% if y %}c{% endif %}'),
            [(TEXT, 'a'), (VAR, 'x'), (TEXT, 'b'), (BLOCK, 'if y'), (TEXT, 'c'), (BLOCK, 'endif')],
        )

    def test_unclosed_tag(self):
        with self.assertRaises(TemplateSyntaxError):
            tokenize('{% if x ')


class RenderTest(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(render('hello'), 'hello')

    def test_variables_and_dotted_lookup(self):
        out = render('{{ user.name }} / {{ site.title }}', user=User('ann', []), site={'title': 'Home'})
        self.assertEqual(out, 'ann / Home')

    def test_filters(self):
        self.assertEqual(render('{{ name|trim|upper }}', name='  bo '), 'BO')
        self.assertEqual(render('{{ tags|join(", ") }}', tags=['a', 'b']), 'a, b')
        self.assertEqual(render('{{ s|truncate(5) }}', s='abcdefgh'), 'ab...')
        self.assertEqual(render('{{ items|length }}', items=[1, 2, 3]), '3')

    def test_pipe_inside_quoted_argument(self):
        self.assertEqual(render('{{ xs|join(" | ") }}', xs=['a', 'b']), 'a | b')

    def test_if_else(self):
        src = '{% if user.tags %}tagged{% else %}plain{% endif %}'
        self.assertEqual(render(src, user=User('a', ['x'])), 'tagged')
        self.assertEqual(render(src, user=User('a', [])), 'plain')

    def test_for_loop(self):
        out = render('{% for t in tags %}[{{ t }}]{% endfor %}', tags=['a', 'b'])
        self.assertEqual(out, '[a][b]')

    def test_nested_for_and_if(self):
        src = (
            '{% for row in rows %}{% for c in row %}'
            '{% if c %}{{ c }}{% else %}-{% endif %}'
            '{% endfor %};{% endfor %}'
        )
        self.assertEqual(render(src, rows=[[1, 0], [0, 2]]), '1-;-2;')

    def test_autoescape(self):
        self.assertEqual(render('{{ v }}', v='<b>&</b>'), '&lt;b&gt;&amp;&lt;/b&gt;')

    def test_safe_and_markup_skip_escaping(self):
        self.assertEqual(render('{{ v|safe }}', v='<i>x</i>'), '<i>x</i>')
        self.assertEqual(render('{{ v }}', v=Markup('<i>x</i>')), '<i>x</i>')

    def test_escape_filter_forces_escaping(self):
        self.assertEqual(render('{{ v|safe|e }}', v='<i>'), '&lt;i&gt;')

    def test_autoescape_off(self):
        env = Environment(autoescape=False)
        self.assertEqual(env.from_string('{{ v }}').render(v='<b>'), '<b>')
        self.assertEqual(env.from_string('{{ v|escape }}').render(v='<b>'), '&lt;b&gt;')

    def test_custom_filter(self):
        env = Environment(filters={'double': lambda v: v * 2})
        self.assertEqual(env.from_string('{{ n|double }}').render(n=21), '42')

    def test_none_renders_empty(self):
        self.assertEqual(render('[{{ v }}]', v=None), '[]')

    def test_errors(self):
        with self.assertRaises(UndefinedError):
            render('{{ missing }}')
        with self.assertRaises(UndefinedError):
            render('{{ user.nope }}', user=User('a', []))
        with self.assertRaises(TemplateSyntaxError):
            render('{% for x in xs %}')
        with self.assertRaises(TemplateSyntaxError):
            render('{% endif %}')
        with self.assertRaises(TemplateSyntaxError):
            render('{{ x|nosuch }}', x=1)
