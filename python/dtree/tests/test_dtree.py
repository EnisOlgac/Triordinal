"""Tests for DTree 3.0, against a brute-force model of the same tree."""

import glob
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dlist"))

from triordinal.dtree import DNode, DTree  # noqa: E402
from triordinal.dtree.two_lists import DTree as DTree2  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


class Model:
    """Parent and ordered kids in plain Python lists."""

    def __init__(self, root):
        self.root, self.up, self.kids = root, {root: None}, {root: []}

    def add(self, p, c, i):
        self.up[c], self.kids[c] = p, []
        self.kids[p].insert(i, c)

    def preorder(self):
        out, stack = [], [self.root]
        while stack:
            v = stack.pop()
            out.append(v)
            stack.extend(reversed(self.kids[v]))
        return out

    def reaches(self, u, v):
        v = self.up[v]
        while v is not None:
            if v == u:
                return True
            v = self.up[v]
        return False

    def subtree(self, v):
        out, stack = [], [v]
        while stack:
            x = stack.pop()
            out.append(x)
            stack.extend(reversed(self.kids[x]))
        return out


class DTreeTest(unittest.TestCase):
    def check(self, t, m, rng, queries=300):
        self.assertEqual(t.q1, m.preorder())
        names = list(m.up)
        for _ in range(queries):
            u, v = rng.choice(names), rng.choice(names)
            self.assertEqual(t.can_reach(u, v), m.reaches(u, v), (u, v))
        for v in rng.sample(names, min(20, len(names))):
            self.assertEqual(t.children(v), m.kids[v])
            self.assertEqual(t.get_parent(v), m.up[v])
            self.assertEqual(t.subtree(v), m.subtree(v))
        tops = {}
        for v in names:                                  # vertical runs: top of the run of only kids
            x = v
            while m.up[x] is not None and len(m.kids[m.up[x]]) == 1:
                x = m.up[x]
            tops.setdefault(x, []).append(v)
        for top, members in tops.items():
            run = t.get_node(top).run
            if len(members) == 1:
                self.assertIsNone(run, top)               # a run of one vertex has no object
                continue
            self.assertEqual(run.top.name, top)
            self.assertEqual(run.size, len(members), top)
            for v in members:
                self.assertIs(t.get_node(v).run, run, v)
        for _ in range(5):                               # constructed nodes, built for the query
            s = rng.sample(names, min(len(names), rng.randrange(1, 6)))
            vmin, vmax, umin, umax = t.vmin(s), t.vmax(s), t.umin(s), t.umax(s)
            for x in rng.sample(names, min(10, len(names))):
                self.assertEqual(vmin.reaches_all(x), all(m.reaches(x, y) for y in s), (x, s))
                self.assertEqual(vmax.reaches_some(x), any(m.reaches(x, y) for y in s), (x, s))
                self.assertEqual(umax.reached_by_all(x), all(m.reaches(y, x) for y in s), (x, s))
                self.assertEqual(umin.reached_by_some(x), any(m.reaches(y, x) for y in s), (x, s))
                cov = umin.covering(x)
                if cov is not None:
                    self.assertTrue(m.reaches(cov, x) and cov in s)

    def run_random(self, positions, seed, steps=1500, deep=False):
        rng = random.Random(seed)
        t, m = DTree("K", positions), Model("r")
        t.insert("r", "n0")
        m.add("r", "n0", 0)
        nxt = 1
        for step in range(steps):
            names = list(m.up)
            op = rng.random()
            if op < 0.55 or len(names) < 4:
                p = names[-1] if deep and rng.random() < 0.7 else rng.choice(names)
                c = f"n{nxt}"
                nxt += 1
                how = rng.randrange(4)
                kids = m.kids[p]
                if how == 0:
                    t.insert(p, c)
                    m.add(p, c, len(kids))
                elif how == 1:
                    t.insert_first(p, c)
                    m.add(p, c, 0)
                elif kids:
                    s = rng.choice(kids)
                    i = kids.index(s)
                    if how == 2:
                        t.insert_before(s, c)
                        m.add(p, c, i)
                    else:
                        t.insert_after(s, c)
                        m.add(p, c, i + 1)
                else:
                    t.insert(p, c)
                    m.add(p, c, 0)
            elif op < 0.7:
                v = rng.choice(names)
                if v == "r":
                    continue
                p = m.up[v]
                i = m.kids[p].index(v)
                m.kids[p][i:i + 1] = m.kids[v]
                for k in m.kids[v]:
                    m.up[k] = p
                del m.up[v], m.kids[v]
                t.delete(v)
            elif op < 0.8:
                v = rng.choice(names)
                if v == "r":
                    continue
                gone = m.subtree(v)
                m.kids[m.up[v]].remove(v)
                for x in gone:
                    del m.up[x], m.kids[x]
                self.assertEqual(t.delete_subtree(v), gone)
            else:
                u, p = rng.choice(names), rng.choice(names)
                if u == "r" or u == p or m.reaches(u, p):
                    with self.assertRaises(ValueError):
                        t.cut_n_paste(u, p)
                    continue
                m.kids[m.up[u]].remove(u)
                m.up[u] = p
                m.kids[p].append(u)
                t.cut_n_paste(u, p)
            if step % 50 == 0:
                self.check(t, m, rng)
        self.check(t, m, rng, 2000)
        self.assertEqual(len(t), len(m.up))

    def test_random_rational(self):
        for seed in range(4):
            self.run_random("rational", seed)

    def test_random_integer(self):
        for seed in range(4):
            self.run_random("integer", seed)

    def test_deep(self):
        for seed in range(3):
            self.run_random("rational", 11 + seed, deep=True)
            self.run_random("integer", 21 + seed, deep=True)

    def test_chain_is_one_vertical_run(self):
        t = DTree("C")
        t.insert("r", "c0")
        for i in range(1, 1000):
            t.insert(f"c{i - 1}", f"c{i}")
        self.assertEqual(t.climb_steps, 0)                # every parent had no kids yet
        t.climb_steps = 0
        self.assertTrue(t.can_reach("c400", "c900"))
        self.assertFalse(t.can_reach("c400", "c300"))
        self.assertLessEqual(t.climb_steps, 1)            # one step to the top of the run
        t.run_steps = 0
        t.insert("c2", "x")                               # cut near the top: only r..c2 move
        self.assertLess(t.run_steps, 10)
        self.assertEqual(t.get_node("c500").run.top.name, "c3")
        t.delete("x")                                     # one kid again: the runs join
        self.assertEqual(t.get_node("c500").run.top.name, "r")

    def test_examples_match_two_lists(self):
        """Every .csx example gives the same Q1 and the same reachability as DTree 2.x."""
        files = sorted(glob.glob(str(EXAMPLES / "*.csx")))
        self.assertTrue(files)
        for path in files:
            t, old = DTree.from_file(path), DTree2.from_file(path)
            self.assertEqual(t.q1, old.q1, path)
            for u in t.q1:
                for v in t.q1:
                    self.assertEqual(t.can_reach(u, v), old.can_reach(u, v), (path, u, v))

    def test_handles(self):
        t = DTree("H")
        a = t.insert("r", "a")
        self.assertIsInstance(a, DNode)
        b = t.insert(a, "b")
        self.assertTrue(t.can_reach("r", b))
        self.assertEqual(a.children, [b])
        self.assertIs(b.parent, a)
        t.delete(b)
        self.assertFalse(b.is_in_tree)
        with self.assertRaises(KeyError):
            t.can_reach(b, a)

    def test_errors(self):
        t = DTree("E")
        with self.assertRaises(ValueError):
            t.insert("r", "r")
        t.insert("r", "a")
        with self.assertRaises(ValueError):
            t.insert("r", "a")                            # already in the tree
        with self.assertRaises(KeyError):
            t.insert("zz", "b")                           # unknown parent
        with self.assertRaises(ValueError):
            t.insert_after("r", "b")                      # the root has no siblings
        with self.assertRaises(ValueError):
            t.delete("r")
        with self.assertRaises(ValueError):
            t.cut_n_paste("r", "a")
        with self.assertRaises(ValueError):
            t.insert("a", "")
        with self.assertRaises(TypeError):
            t.insert("a", 5)
        with self.assertRaises(ValueError):
            t.add_line("no operator")
        with self.assertRaises(ValueError):
            t.vmin([])


if __name__ == "__main__":
    unittest.main()
