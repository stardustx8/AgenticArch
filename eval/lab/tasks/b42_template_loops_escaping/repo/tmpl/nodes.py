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


class For(Node):
    def __init__(self, target, expr, body):
        self.target = target
        self.expr = expr
        self.body = body

    def render(self, context, env):
        out = []
        for item in self.expr.evaluate(context, env.filters):
            context.set(self.target, item)
            out.append(render_nodes(self.body, context, env))
        return ''.join(out)


def render_nodes(nodes, context, env):
    return ''.join(node.render(context, env) for node in nodes)
