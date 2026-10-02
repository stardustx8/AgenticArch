import heapq

from deps.errors import CycleError


def execution_order(graph):
    # Every task appears after all of its prerequisites; whenever several tasks are
    # ready the alphabetically smallest goes first (lexicographically smallest order).
    graph.validate()
    waiting = {name: set(graph.prerequisites(name)) for name in graph.tasks()}
    dependents = {name: [] for name in waiting}
    for name, deps in waiting.items():
        for dep in deps:
            dependents[dep].append(name)
    ready = [name for name, deps in waiting.items() if not deps]
    heapq.heapify(ready)
    order = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for child in dependents[name]:
            waiting[child].discard(name)
            if not waiting[child]:
                heapq.heappush(ready, child)
    if len(order) < len(waiting):
        done = set(order)
        raise CycleError(_find_cycle(graph, [name for name in waiting if name not in done]))
    return order


def _find_cycle(graph, blocked):
    # Every blocked task waits on at least one other blocked task, so following
    # 'depends on' edges inside the blocked set must eventually revisit a task.
    blocked = set(blocked)
    path = []
    seen = {}
    name = min(blocked)
    while name not in seen:
        seen[name] = len(path)
        path.append(name)
        name = min(dep for dep in graph.prerequisites(name) if dep in blocked)
    cycle = path[seen[name]:]
    start = cycle.index(min(cycle))
    cycle = cycle[start:] + cycle[:start]
    return cycle + [cycle[0]]


def batches(graph):
    # Group tasks into waves; every task's prerequisites are in earlier waves.
    level = {}
    for name in execution_order(graph):
        level[name] = 1 + max((level[dep] for dep in graph.prerequisites(name)), default=-1)
    waves = {}
    for name, lvl in level.items():
        waves.setdefault(lvl, []).append(name)
    return [sorted(waves[lvl]) for lvl in sorted(waves)]
