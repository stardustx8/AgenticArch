class DependencyError(Exception):
    pass


class UnknownTaskError(DependencyError):
    def __init__(self, name):
        super().__init__('unknown task: %r' % (name,))
        self.name = name


class CycleError(DependencyError):
    def __init__(self, cycle):
        self.cycle = list(cycle)
        super().__init__('dependency cycle: ' + ' -> '.join(self.cycle))
