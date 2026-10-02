from dataclasses import dataclass


class CalcSyntaxError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    kind: str  # NUM, OP, LPAREN, RPAREN or END
    value: str
    pos: int


OPERATORS = '+-*/'
NUMBER_CHARS = '0123456789.'


def tokenize(text):
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in NUMBER_CHARS:
            start = i
            while i < len(text) and text[i] in NUMBER_CHARS:
                i += 1
            literal = text[start:i]
            if literal.count('.') > 1 or literal == '.':
                raise CalcSyntaxError('bad number %r at %d' % (literal, start))
            tokens.append(Token('NUM', literal, start))
            continue
        if ch in OPERATORS:
            tokens.append(Token('OP', ch, i))
        elif ch == '(':
            tokens.append(Token('LPAREN', ch, i))
        elif ch == ')':
            tokens.append(Token('RPAREN', ch, i))
        else:
            raise CalcSyntaxError('unexpected character %r at %d' % (ch, i))
        i += 1
    tokens.append(Token('END', '', len(text)))
    return tokens
