from deps.errors import UnknownTaskError


class TaskGraph:
    def __init__(self):
        self._deps = {}

    def add_task(self, name, depends_on=()):
        # Calling add_task again for the same name adds more prerequisites.
        self._deps.setdefault(name, set()).update(depends_on)

    def tasks(self):
        return sorted(self._deps)

    def prerequisites(self, name):
        if name not in self._deps:
            raise UnknownTaskError(name)
        return sorted(self._deps[name])

    def validate(self):
        for name in self.tasks():
            for dep in self.prerequisites(name):
                if dep not in self._deps:
                    raise UnknownTaskError(dep)
