"""A small template engine: variables, filters, if/for blocks and HTML autoescaping."""
from .environment import Environment, Template
from .errors import TemplateError, TemplateSyntaxError, UndefinedError
from .escaping import Markup, escape

__all__ = [
    'Environment',
    'Markup',
    'Template',
    'TemplateError',
    'TemplateSyntaxError',
    'UndefinedError',
    'escape',
    'render',
]


def render(source, data=None, **kwargs):
    """Render ``source`` once with a default (autoescaping) environment."""
    return Environment().from_string(source).render(data, **kwargs)
