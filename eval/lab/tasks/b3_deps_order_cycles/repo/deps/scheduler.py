from deps.errors import CycleError


def execution_order(graph):
    # Every task appears after all of its prerequisites.
    graph.validate()
    order = []
    done = set()
    in_progress = set()

    def visit(name):
        if name in done:
            return
        if name in in_progress:
            raise CycleError(sorted(in_progress))
        in_progress.add(name)
        for dep in graph.prerequisites(name):
            visit(dep)
        in_progress.discard(name)
        done.add(name)
        order.append(name)

    for name in graph.tasks():
        visit(name)
    return order


def batches(graph):
    # Group tasks into waves; every task's prerequisites are in earlier waves.
    level = {}
    for name in execution_order(graph):
        level[name] = 1 + max((level[dep] for dep in graph.prerequisites(name)), default=-1)
    waves = {}
    for name, lvl in level.items():
        waves.setdefault(lvl, []).append(name)
    return [sorted(waves[lvl]) for lvl in sorted(waves)]
