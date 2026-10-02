import unittest

from tmpl import TemplateSyntaxError, UndefinedError, render


class HiddenLoopHelpersTest(unittest.TestCase):
    def test_counters_and_length(self):
        src = '{% for x in xs %}{{ loop.index }}:{{ loop.index0 }}:{{ x }}/{{ loop.length }} {% endfor %}'
        self.assertEqual(render(src, xs=['a', 'b', 'c']), '1:0:a/3 2:1:b/3 3:2:c/3 ')

    def test_first_and_last(self):
        src = '{% for x in xs %}{% if loop.first %}<{% endif %}{{ x }}{% if loop.last %}>{% else %},{% endif %}{% endfor %}'
        self.assertEqual(render(src, xs=[1, 2, 3]), '<1,2,3>')

    def test_single_item_is_first_and_last(self):
        src = '{% for x in xs %}{{ loop.first }}-{{ loop.last }}{% endfor %}'
        self.assertEqual(render(src, xs=['only']), 'True-True')

    def test_generator_input(self):
        src = '{% for n in nums %}{{ n }}{% if loop.last %}.{% else %},{% endif %}{% endfor %}'
        self.assertEqual(render(src, nums=(n * n for n in range(1, 4))), '1,4,9.')

    def test_iterator_length(self):
        self.assertEqual(render('{% for n in nums %}{{ loop.length }}{% endfor %}', nums=iter([5, 6])), '22')

    def test_nested_loops_have_their_own_loop(self):
        src = '{% for row in rows %}{% for c in row %}{{ loop.index }}{% endfor %}@{{ loop.index }};{% endfor %}'
        self.assertEqual(render(src, rows=[['a', 'b'], ['c']]), '12@1;1@2;')

    def test_nested_loop_can_reach_outer_variables(self):
        src = '{% for row in rows %}{% for c in row %}{{ row|length }}{{ c }}{% endfor %}{% endfor %}'
        self.assertEqual(render(src, rows=[['a', 'b']]), '2a2b')


class HiddenLoopScopeTest(unittest.TestCase):
    def test_loop_variable_does_not_clobber_outer(self):
        src = '{% for x in xs %}{{ x }}{% endfor %}|{{ x }}'
        self.assertEqual(render(src, xs=['a', 'b'], x='outer'), 'ab|outer')

    def test_loop_variable_undefined_after_loop(self):
        with self.assertRaises(UndefinedError):
            render('{% for x in xs %}{{ x }}{% endfor %}{{ x }}', xs=[1])

    def test_loop_helper_undefined_after_loop(self):
        with self.assertRaises(UndefinedError):
            render('{% for x in xs %}{% endfor %}{{ loop.index }}', xs=[1])


class HiddenForElseTest(unittest.TestCase):
    SRC = '{% for x in xs %}{{ x }}{% else %}none{% endfor %}'

    def test_else_only_when_empty(self):
        self.assertEqual(render(self.SRC, xs=[]), 'none')
        self.assertEqual(render(self.SRC, xs=[1, 2]), '12')

    def test_else_for_empty_generator(self):
        self.assertEqual(render(self.SRC, xs=(x for x in [])), 'none')

    def test_if_else_inside_for_else(self):
        src = '{% for x in xs %}{% if x %}y{% else %}n{% endif %}{% else %}empty{% endfor %}'
        self.assertEqual(render(src, xs=[1, 0]), 'yn')
        self.assertEqual(render(src, xs=[]), 'empty')

    def test_for_else_inside_if_else(self):
        src = '{% if show %}{% for x in xs %}{{ x }}{% else %}-{% endfor %}{% else %}hidden{% endif %}'
        self.assertEqual(render(src, show=True, xs=[]), '-')
        self.assertEqual(render(src, show=False, xs=[1]), 'hidden')

    def test_unterminated_for_else(self):
        with self.assertRaises(TemplateSyntaxError):
            render('{% for x in xs %}a{% else %}b', xs=[])
