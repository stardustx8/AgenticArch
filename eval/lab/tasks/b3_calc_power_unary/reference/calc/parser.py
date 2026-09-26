from fractions import Fraction

from calc.tokenizer import CalcSyntaxError, tokenize

# AST nodes are tuples: ('num', Fraction), ('neg', operand) or ('bin', op, left, right).


class Parser:
    def __init__(self, text):
        self.tokens = tokenize(text)
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def at_op(self, ops):
        token = self.peek()
        return token.kind == 'OP' and token.value in ops

    def expect(self, kind):
        token = self.peek()
        if token.kind != kind:
            raise CalcSyntaxError('expected %s at %d' % (kind, token.pos))
        return self.advance()

    def parse(self):
        node = self.expr()
        self.expect('END')
        return node

    # expr := term (('+' | '-') term)*
    def expr(self):
        node = self.term()
        while self.at_op('+-'):
            op = self.advance().value
            node = ('bin', op, node, self.term())
        return node

    # term := unary (('*' | '/') unary)*
    def term(self):
        node = self.unary()
        while self.at_op('*/'):
            op = self.advance().value
            node = ('bin', op, node, self.unary())
        return node

    # unary := ('+' | '-') unary | power
    def unary(self):
        if self.at_op('+-'):
            op = self.advance().value
            operand = self.unary()
            return ('neg', operand) if op == '-' else operand
        return self.power()

    # power := atom ('^' unary)?   (right-associative, tighter than unary minus)
    def power(self):
        base = self.atom()
        if self.at_op('^'):
            self.advance()
            return ('bin', '^', base, self.unary())
        return base

    # atom := NUMBER | '(' expr ')'
    def atom(self):
        token = self.peek()
        if token.kind == 'NUM':
            self.advance()
            return ('num', Fraction(token.value))
        if token.kind == 'LPAREN':
            self.advance()
            node = self.expr()
            self.expect('RPAREN')
            return node
        raise CalcSyntaxError('unexpected %s at %d' % (token.value or 'end of input', token.pos))


def parse(text):
    return Parser(text).parse()
