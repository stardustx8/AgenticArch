from .escaping import escape


class Node:
    def render(self, context, env):
        raise NotImplementedError


class Text(Node):
    def __init__(self, text):
        self.text = text

    def render(self, context, env):
        return self.text


class Output(Node):
    def __init__(self, expr):
        self.expr = expr

    def render(self, context, env):
        value = self.expr.evaluate(context, env.filters)
        if value is None:
            return ''
        return escape(value) if env.autoescape else str(value)


class If(Node):
    def __init__(self, expr, body, else_body):
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def render(self, context, env):
        branch = self.body if self.expr.evaluate(context, env.filters) else self.else_body
        return render_nodes(branch, context, env)


class LoopInfo:
    """The ``loop`` variable available inside a for body."""

    def __init__(self, index0, length):
        self.index0 = index0
        self.index = index0 + 1
        self.length = length
        self.first = index0 == 0
        self.last = index0 == length - 1


class For(Node):
    def __init__(self, target, expr, body, else_body=()):
        self.target = target
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def render(self, context, env):
        # Materialise first: generators have no len() and loop.last needs the length.
        items = list(self.expr.evaluate(context, env.filters))
        if not items:
            return render_nodes(self.else_body, context, env)
        out = []
        for index0, item in enumerate(items):
            # A fresh scope per iteration keeps the target and ``loop`` from leaking
            # out of the loop or clobbering outer variables of the same name.
            context.push({self.target: item, 'loop': LoopInfo(index0, len(items))})
            try:
                out.append(render_nodes(self.body, context, env))
            finally:
                context.pop()
        return ''.join(out)


def render_nodes(nodes, context, env):
    return ''.join(node.render(context, env) for node in nodes)
