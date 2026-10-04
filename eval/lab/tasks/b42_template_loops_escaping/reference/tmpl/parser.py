from .errors import TemplateSyntaxError
from .expressions import parse_expression
from .lexer import TEXT, VAR
from .nodes import For, If, Output, Text


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        nodes, _ = self._parse_until(())
        return nodes

    def _parse_until(self, stop_tags):
        """Parse nodes until one of ``stop_tags``; returns (nodes, tag that stopped)."""
        nodes = []
        while self.pos < len(self.tokens):
            kind, value = self.tokens[self.pos]
            self.pos += 1
            if kind == TEXT:
                nodes.append(Text(value))
            elif kind == VAR:
                nodes.append(Output(parse_expression(value)))
            else:
                word = value.split(None, 1)[0] if value else ''
                rest = value[len(word):].strip()
                if word in stop_tags:
                    return nodes, word
                if word == 'if':
                    nodes.append(self._parse_if(rest))
                elif word == 'for':
                    nodes.append(self._parse_for(rest))
                else:
                    raise TemplateSyntaxError(f'unexpected tag {word!r}')
        if stop_tags:
            raise TemplateSyntaxError(f'missing {stop_tags[-1]!r}')
        return nodes, None

    def _parse_if(self, rest):
        if not rest:
            raise TemplateSyntaxError('if needs a condition')
        condition = parse_expression(rest)
        body, end = self._parse_until(('else', 'endif'))
        else_body = []
        if end == 'else':
            else_body, _ = self._parse_until(('endif',))
        return If(condition, body, else_body)

    def _parse_for(self, rest):
        target, sep, source = rest.partition(' in ')
        target = target.strip()
        if not sep or not target.isidentifier():
            raise TemplateSyntaxError(f'bad for tag: {rest!r}')
        iterable = parse_expression(source.strip())
        body, end = self._parse_until(('else', 'endfor'))
        else_body = []
        if end == 'else':
            else_body, _ = self._parse_until(('endfor',))
        return For(target, iterable, body, else_body)
