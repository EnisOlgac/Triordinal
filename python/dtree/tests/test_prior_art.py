"""Tests for the prior-art contenders of the benchmarks, against brute force."""

import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "dlist"))

from triordinal.dtree.prior_art import EulerTour, EulerTourInt, EulerTourNum, IntList, NumList, PrePostNumbers  # noqa: E402


def random_parents(n, seed, depth=None):
    rnd = random.Random(seed)
    parent = {}
    for i in range(1, n):
        if depth is not None and i < depth:
            parent[i] = i - 1
        else:
            parent[i] = rnd.randrange(i if depth is None else min(depth, i))
    return parent, rnd


def ancestors(parent, v):
    out = set()
    while v in parent:
        v = parent[v]
        out.add(v)
    return out


class TestContenders(unittest.TestCase):
    def check(self, n, seed, depth=None):
        parent, rnd = random_parents(n, seed, depth)
        e, p, ei = EulerTour(), PrePostNumbers(), EulerTourInt()
        ef, ed = EulerTourNum(kind="float"), EulerTourNum(kind="decimal")
        for c, a in parent.items():
            for t in (e, ei, ef, ed):
                t.insert(f"n{a}", f"n{c}")
            p.insert(a, c)
        self.assertEqual(ei.nodes(), e.nodes())
        self.assertEqual(ef.nodes(), e.nodes())
        self.assertEqual(ed.nodes(), e.nodes())
        anc = {v: ancestors(parent, v) for v in range(n)}
        self.assertEqual(len(e.nodes()), n)
        for _ in range(400):
            u, v = rnd.randrange(n), rnd.randrange(n)
            expected = u in anc[v]
            self.assertEqual(e.can_reach(f"n{u}", f"n{v}"), expected, (u, v))
            self.assertEqual(p.can_reach(u, v), expected, (u, v))
            self.assertEqual(ei.can_reach(f"n{u}", f"n{v}"), expected, (u, v))
            self.assertEqual(ef.can_reach(f"n{u}", f"n{v}"), expected, (u, v))
            self.assertEqual(ed.can_reach(f"n{u}", f"n{v}"), expected, (u, v))
        for k in (1, 2, 5, 20):
            S = rnd.sample(range(n), k)
            es = e.euler_set(f"n{s}" for s in S)
            ns = p.number_set(S)
            for x in range(n):
                h = e.get_node(f"n{x}")
                all_ = all(x in anc[s] for s in S)
                some = any(x in anc[s] for s in S)
                by_all = all(s in anc[x] for s in S)
                by_some = any(s in anc[x] for s in S)
                self.assertEqual((es.reaches_all(h), ns.reaches_all(x)), (all_, all_), (x, S))
                self.assertEqual((es.reaches_some(h), ns.reaches_some(x)), (some, some), (x, S))
                self.assertEqual((es.reached_by_all(h), ns.reached_by_all(x)), (by_all, by_all), (x, S))
                self.assertEqual((es.reached_by_some(h), ns.reached_by_some(x)), (by_some, by_some), (x, S))

    def test_random_trees(self):
        for seed in range(10):
            self.check(120, seed)

    def test_deep_trees(self):
        for seed in range(5):
            self.check(300, seed, depth=150)

    def test_lazy_recomputation(self):
        p = PrePostNumbers()
        for i in range(1, 50):
            p.insert(i - 1, i)
        self.assertEqual(p.recomputations, 0)          # insertions only mark the numbers stale
        for _ in range(10):
            p.can_reach(0, 49)
        self.assertEqual(p.recomputations, 1)          # one traversal for all ten queries
        p.insert(0, 50)
        self.assertFalse(p.can_reach(49, 50))
        self.assertEqual(p.recomputations, 2)

    def test_euler_chain_stays_ordered(self):
        e = EulerTour()
        for i in range(1, 3000):
            e.insert(f"n{i - 1}", f"n{i}")
        c = e.list.first
        while c.next is not None:
            self.assertTrue(e.list._lt(c, c.next))
            c = c.next
        self.assertTrue(e.can_reach("n0", "n2999") and not e.can_reach("n2999", "n0"))


class TestIntList(unittest.TestCase):
    def labels_increase(self, q):
        c = q.first
        while c.next is not None:
            if not c.label < c.next.label:
                return False
            c = c.next
        return True

    def test_random_insertions_with_hot_spots(self):
        for msd in (0, 2, 10):
            self._hot_spots(msd)

    def _hot_spots(self, msd):
        rnd = random.Random(3)
        q, ref, cells = IntList("Q", msd), [], {}
        for i in range(30000):
            name = f"v{i}"
            if not ref or rnd.random() < 0.2:
                cells[name] = q._insert_cell_after(name, q.first)
                ref.insert(0, name)
            else:
                j = rnd.choice([0, len(ref) // 2, len(ref) - 1, rnd.randrange(len(ref))])
                cells[name] = q._insert_cell_after(name, cells[ref[j]])
                ref.insert(j + 1, name)
        self.assertEqual(list(q), ref)
        self.assertTrue(self.labels_increase(q))
        self.assertGreater(q.renumber_count, 0)

    def test_deep_chain_and_appends(self):
        e = EulerTourInt()
        for i in range(1, 5000):
            e.insert(f"n{i - 1}", f"n{i}")
        self.assertTrue(self.labels_increase(e.list))
        self.assertTrue(e.can_reach("n0", "n4999") and not e.can_reach("n4999", "n0"))
        q = IntList("A")
        c = q.first
        for i in range(5000):
            c = q._insert_cell_after(f"a{i}", c)        # append at the end
        self.assertTrue(self.labels_increase(q))


class TestNumList(unittest.TestCase):
    def labels_increase(self, q):
        c = q.first.next
        while c.next is not q.last:
            if not c.label < c.next.label:
                return False
            c = c.next
        return True

    def test_patterns(self):
        for kind, msd in (("float", 0), ("float", 2), ("float", 10), ("decimal", 0), ("decimal", 10)):
            rnd = random.Random(5)
            q, ref, cells = NumList("Q", kind, msd), [], {}
            for i in range(20000):
                name = f"v{i}"
                if not ref or rnd.random() < 0.2:
                    cells[name] = q._insert_cell_after(name, q.first)
                    ref.insert(0, name)
                else:
                    j = rnd.choice([0, len(ref) // 2, len(ref) - 1, rnd.randrange(len(ref))])
                    cells[name] = q._insert_cell_after(name, cells[ref[j]])
                    ref.insert(j + 1, name)
            self.assertEqual(list(q), ref, kind)
            self.assertTrue(self.labels_increase(q), kind)
            self.assertGreater(q.renumber_count, 0, kind)
            e = EulerTourNum(kind=kind, msd=msd)
            for i in range(1, 3000):
                e.insert(f"n{i - 1}", f"n{i}")
            self.assertTrue(self.labels_increase(e.list), kind)
            self.assertTrue(e.can_reach("n0", "n2999") and not e.can_reach("n2999", "n0"), kind)


if __name__ == "__main__":
    unittest.main()
