from calc.parser import parse


def evaluate_node(node):
    kind = node[0]
    if kind == 'num':
        return node[1]
    if kind == 'bin':
        op = node[1]
        left = evaluate_node(node[2])
        right = evaluate_node(node[3])
        if op == '+':
            return left + right
        if op == '-':
            return left - right
        if op == '*':
            return left * right
        if op == '/':
            if right == 0:
                raise ZeroDivisionError('division by zero')
            return left / right
    raise ValueError('unknown node: %r' % (node,))


def evaluate(text):
    return evaluate_node(parse(text))
