import unittest

from deps import CycleError, DependencyError, TaskGraph, UnknownTaskError, batches, execution_order


def build(spec):
    graph = TaskGraph()
    for name, deps in spec.items():
        graph.add_task(name, deps)
    return graph


class TestOrder(unittest.TestCase):
    def assertValidOrder(self, graph, order):
        self.assertEqual(sorted(order), graph.tasks())
        position = {name: i for i, name in enumerate(order)}
        for name in order:
            for dep in graph.prerequisites(name):
                self.assertLess(position[dep], position[name])

    def test_chain(self):
        graph = build({'c': ['b'], 'b': ['a'], 'a': []})
        self.assertEqual(execution_order(graph), ['a', 'b', 'c'])

    def test_diamond_is_valid(self):
        graph = build({'deploy': ['test', 'package'], 'test': ['build'], 'package': ['build'], 'build': []})
        self.assertValidOrder(graph, execution_order(graph))

    def test_unknown_dependency(self):
        graph = build({'a': ['missing']})
        with self.assertRaises(UnknownTaskError):
            execution_order(graph)

    def test_cycle_detected(self):
        graph = build({'a': ['b'], 'b': ['a']})
        with self.assertRaises(CycleError) as ctx:
            execution_order(graph)
        self.assertIsInstance(ctx.exception, DependencyError)

    def test_add_task_merges(self):
        graph = TaskGraph()
        graph.add_task('a', ['b'])
        graph.add_task('a', ['c'])
        graph.add_task('b')
        graph.add_task('c')
        self.assertEqual(graph.prerequisites('a'), ['b', 'c'])


class TestBatches(unittest.TestCase):
    def test_waves(self):
        graph = build({'deploy': ['test'], 'test': ['build'], 'build': [], 'lint': []})
        self.assertEqual(batches(graph), [['build', 'lint'], ['test'], ['deploy']])


if __name__ == '__main__':
    unittest.main()
