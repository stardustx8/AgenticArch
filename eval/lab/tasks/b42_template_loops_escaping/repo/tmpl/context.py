from collections.abc import Mapping

from .errors import UndefinedError


class Context:
    """A stack of variable scopes; lookups search from the innermost scope out."""

    def __init__(self, data=None):
        self._scopes = [dict(data or {})]

    def push(self, values=None):
        self._scopes.append(dict(values or {}))

    def pop(self):
        if len(self._scopes) == 1:
            raise RuntimeError('cannot pop the root scope')
        self._scopes.pop()

    def set(self, name, value):
        self._scopes[-1][name] = value

    def lookup(self, name):
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise UndefinedError(f'{name!r} is undefined')

    def resolve(self, path):
        """Resolve a dotted path such as ``user.address.city``."""
        head, *rest = path.split('.')
        value = self.lookup(head)
        for attr in rest:
            value = _get(value, attr, path)
        return value


def _get(value, attr, path):
    if isinstance(value, Mapping):
        if attr in value:
            return value[attr]
    elif hasattr(value, attr):
        return getattr(value, attr)
    raise UndefinedError(f'{path!r} is undefined')
