import itertools
import unittest

from deps import CycleError, TaskGraph, batches, execution_order


def build(spec):
    graph = TaskGraph()
    for name, deps in spec.items():
        graph.add_task(name, deps)
    return graph


class TestLexicographicOrder(unittest.TestCase):
    def test_ready_tasks_taken_alphabetically(self):
        graph = build({'a': ['z'], 'b': [], 'z': []})
        self.assertEqual(execution_order(graph), ['b', 'z', 'a'])

    def test_release_pipeline(self):
        graph = build({
            'deploy': ['build', 'test'], 'test': ['build'], 'build': [], 'lint': [], 'docs': [],
        })
        self.assertEqual(execution_order(graph), ['build', 'docs', 'lint', 'test', 'deploy'])

    def test_newly_ready_task_competes_with_waiting_ones(self):
        graph = build({'b': ['a'], 'c': [], 'a': []})
        self.assertEqual(execution_order(graph), ['a', 'b', 'c'])

    def test_empty_graph(self):
        self.assertEqual(execution_order(TaskGraph()), [])
        self.assertEqual(batches(TaskGraph()), [])

    def test_matches_brute_force_minimum(self):
        spec = {'e': ['a'], 'd': ['b', 'e'], 'c': [], 'b': ['c'], 'a': [], 'f': ['c']}
        graph = build(spec)
        valid = []
        for perm in itertools.permutations(sorted(spec)):
            pos = {name: i for i, name in enumerate(perm)}
            if all(pos[dep] < pos[name] for name in spec for dep in spec[name]):
                valid.append(list(perm))
        self.assertEqual(execution_order(graph), min(valid))


class TestCycleReporting(unittest.TestCase):
    def cycle_of(self, graph):
        with self.assertRaises(CycleError) as ctx:
            execution_order(graph)
        return ctx.exception.cycle

    def assertIsCycle(self, graph, cycle):
        self.assertGreaterEqual(len(cycle), 2)
        self.assertEqual(cycle[0], cycle[-1])
        self.assertEqual(len(set(cycle[:-1])), len(cycle) - 1)
        self.assertEqual(cycle[0], min(cycle))
        for a, b in zip(cycle, cycle[1:]):
            self.assertIn(b, graph.prerequisites(a))

    def test_only_cycle_members_reported(self):
        graph = build({'a': ['b'], 'b': ['c'], 'c': ['b'], 'd': []})
        self.assertEqual(self.cycle_of(graph), ['b', 'c', 'b'])

    def test_self_dependency(self):
        graph = build({'a': ['a'], 'b': []})
        self.assertEqual(self.cycle_of(graph), ['a', 'a'])

    def test_cycle_starts_at_smallest_and_follows_dependencies(self):
        graph = build({'x': ['y'], 'y': ['w'], 'w': ['x']})
        self.assertEqual(self.cycle_of(graph), ['w', 'x', 'y', 'w'])

    def test_tasks_downstream_of_cycle_excluded(self):
        graph = build({'a': ['m'], 'm': ['n'], 'n': ['m'], 'z': ['a']})
        self.assertEqual(self.cycle_of(graph), ['m', 'n', 'm'])

    def test_upstream_tasks_excluded(self):
        graph = build({'base': [], 'p': ['q', 'base'], 'q': ['r'], 'r': ['p']})
        self.assertEqual(self.cycle_of(graph), ['p', 'q', 'r', 'p'])

    def test_tangled_cycles_report_a_real_cycle(self):
        graph = build({'a': ['b'], 'b': ['a', 'c'], 'c': ['a'], 'd': ['c']})
        self.assertIsCycle(graph, self.cycle_of(graph))

    def test_message_shows_the_cycle(self):
        graph = build({'a': ['b'], 'b': ['c'], 'c': ['b']})
        with self.assertRaises(CycleError) as ctx:
            execution_order(graph)
        self.assertIn('b -> c -> b', str(ctx.exception))

    def test_batches_report_cycle_too(self):
        graph = build({'a': ['b'], 'b': ['c'], 'c': ['b'], 'd': []})
        with self.assertRaises(CycleError) as ctx:
            batches(graph)
        self.assertEqual(ctx.exception.cycle, ['b', 'c', 'b'])


if __name__ == '__main__':
    unittest.main()
