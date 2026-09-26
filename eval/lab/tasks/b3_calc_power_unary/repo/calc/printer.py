PRECEDENCE = {'+': 1, '-': 1, '*': 2, '/': 2}
ATOM = 100


def _precedence(node):
    if node[0] == 'bin':
        return PRECEDENCE[node[1]]
    return ATOM


def _format_number(value):
    if value.denominator == 1:
        return str(value.numerator)
    return '(%s)' % (value,)


def to_string(node):
    # Render an AST as infix text using the fewest parentheses that keep its value.
    kind = node[0]
    if kind == 'num':
        return _format_number(node[1])
    if kind == 'bin':
        op, left, right = node[1], node[2], node[3]
        prec = PRECEDENCE[op]
        left_text = to_string(left)
        right_text = to_string(right)
        if _precedence(left) < prec:
            left_text = '(%s)' % (left_text,)
        right_prec = _precedence(right)
        if right_prec < prec or (right_prec == prec and op in '-/'):
            right_text = '(%s)' % (right_text,)
        return '%s %s %s' % (left_text, op, right_text)
    raise ValueError('unknown node: %r' % (node,))
