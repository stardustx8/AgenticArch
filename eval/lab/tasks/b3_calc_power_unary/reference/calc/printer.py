PRECEDENCE = {'+': 1, '-': 1, '*': 2, '/': 2, '^': 4}
UNARY = 3
ATOM = 100


def _precedence(node):
    if node[0] == 'bin':
        return PRECEDENCE[node[1]]
    if node[0] == 'neg':
        return UNARY
    return ATOM


def _format_number(value):
    if value.denominator == 1:
        return str(value.numerator)
    return '(%s)' % (value,)


def _wrap(text):
    return '(%s)' % (text,)


def to_string(node):
    # Render an AST as infix text using the fewest parentheses that keep its value.
    kind = node[0]
    if kind == 'num':
        return _format_number(node[1])
    if kind == 'neg':
        operand = to_string(node[1])
        if _precedence(node[1]) < UNARY:
            operand = _wrap(operand)
        return '-' + operand
    if kind == 'bin':
        op, left, right = node[1], node[2], node[3]
        prec = PRECEDENCE[op]
        left_text = to_string(left)
        right_text = to_string(right)
        left_prec = _precedence(left)
        right_prec = _precedence(right)
        if op == '^':
            # The base must be an atom (so -x and x^y need parentheses); the exponent
            # is parsed as a unary expression, which also makes '^' right-associative.
            if left_prec <= prec:
                left_text = _wrap(left_text)
            if right_prec < UNARY:
                right_text = _wrap(right_text)
        else:
            if left_prec < prec:
                left_text = _wrap(left_text)
            if right_prec < prec or (right_prec == prec and op in '-/'):
                right_text = _wrap(right_text)
        return '%s %s %s' % (left_text, op, right_text)
    raise ValueError('unknown node: %r' % (node,))
