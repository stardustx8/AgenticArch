from .context import Context
from .filters import BUILTIN_FILTERS
from .lexer import tokenize
from .nodes import render_nodes
from .parser import Parser


class Environment:
    """Holds rendering options and the filter table."""

    def __init__(self, autoescape=True, filters=None):
        self.autoescape = autoescape
        self.filters = dict(BUILTIN_FILTERS)
        if filters:
            self.filters.update(filters)

    def from_string(self, source):
        return Template(Parser(tokenize(source)).parse(), self)


class Template:
    def __init__(self, nodes, env):
        self.nodes = nodes
        self.env = env

    def render(self, data=None, **kwargs):
        values = dict(data or {})
        values.update(kwargs)
        return str(render_nodes(self.nodes, Context(values), self.env))
