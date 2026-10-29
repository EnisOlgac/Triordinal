"""Tests for the Python DTree: every query is checked against a brute-force
reference computed from the parent map alone (no projections)."""

import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "dlist"))  # triordinal-dlist from the repository

from triordinal.dtree import SINK, SOURCE, DNode, DTree  # noqa: E402

EXAMPLES = os.path.join(HERE, "..", "..", "..", "examples")


def ref_ancestors(parent, v):
    out = []
    while v in parent:
        out.append(v)
        v = parent[v]
    return out  # [v, ..., child of root]


def ref_preorder(children, root, reverse=False):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        out.append(n)
        kids = children.get(n, [])
        stack.extend(kids if reverse else reversed(kids))
    return out


class Reference:
    """Plain parent/children model mirroring every operation."""

    def __init__(self):
        self.parent, self.children, self.root = {}, {}, None

    def insert(self, u, v):
        if self.root is None:
            self.root = u
        self.parent[v] = u
        self.children.setdefault(u, []).append(v)

    def delete(self, v):
        p = self.parent.pop(v)
        kids = self.children.pop(v, [])
        sib = self.children[p]
        i = sib.index(v)
        sib[i : i + 1] = kids
        for k in kids:
            self.parent[k] = p
        if not sib:
            del self.children[p]

    def delete_subtree(self, v):
        stack, gone = [v], []
        while stack:
            n = stack.pop()
            gone.append(n)
            stack.extend(self.children.pop(n, []))
        p = self.parent[v]
        self.children[p].remove(v)
        if not self.children[p]:
            del self.children[p]
        for n in gone:
            del self.parent[n]

    def insert_after(self, s, v):
        p = self.parent[s]
        sib = self.children[p]
        sib.insert(sib.index(s) + 1, v)
        self.parent[v] = p

    def insert_before(self, s, v):
        p = self.parent[s]
        sib = self.children[p]
        sib.insert(sib.index(s), v)
        self.parent[v] = p

    def move(self, u, p):
        old = self.parent[u]
        self.children[old].remove(u)
        if not self.children[old]:
            del self.children[old]
        self.parent[u] = p
        self.children.setdefault(p, []).append(u)

    def nodes(self):
        return [self.root] + list(self.parent)


def labels_strictly_increase(q):
    prev, cell = q.first, q.first.next
    while cell is not None:
        if not q._lt(prev, cell):
            return False
        prev, cell = cell, cell.next
    return True


def cells(q):
    """All cells between the markers, closing cells included."""
    c = q.first.next
    while c is not q.last:
        yield c
        c = c.next


def raw_cells(q):
    """The whole list: node names, and ")x" for the closing cell of node x."""
    return [c.name if c.name is not None else ")" + c.node.name for c in cells(q)]


def ref_euler(children, root, reverse=False):
    """Pre-order with a closing cell after the subtree of every node that has children."""
    out, stack = [], [(root, False)]
    while stack:
        n, done = stack.pop()
        if done:
            out.append(")" + n)
            continue
        out.append(n)
        kids = children.get(n, [])
        if kids:
            stack.append((n, True))
            stack.extend((k, False) for k in (kids if reverse else reversed(kids)))
    return out


def check(tc, t, ref):
    tc.assertTrue(labels_strictly_increase(t._q1))
    tc.assertTrue(labels_strictly_increase(t._q2))
    tc.assertEqual(raw_cells(t._q1), ref_euler(ref.children, ref.root))
    tc.assertEqual(raw_cells(t._q2), ref_euler(ref.children, ref.root, reverse=True))
    nodes = ref.nodes()
    tc.assertEqual(t.size, len(nodes))
    tc.assertEqual(t.root, ref.root)
    tc.assertEqual(t.q1, ref_preorder(ref.children, ref.root))
    tc.assertEqual(t.q2, ref_preorder(ref.children, ref.root, reverse=True))
    par = dict(ref.parent)
    for v in nodes:
        anc = ref_ancestors(par, v) + [ref.root]  # root has no parent entry
        tc.assertEqual(t.path_to_root(v), anc)
        tc.assertEqual(t.root_to_path(v), anc[::-1])
        tc.assertEqual(t.depth(v), len(anc) - 1)
        tc.assertEqual(t.get_parent(v), par.get(v))
        tc.assertEqual(t.is_leaf(v), v not in ref.children)
    sample = nodes if len(nodes) <= 40 else random.sample(nodes, 40)
    for u in sample:
        for v in sample:
            anc_v = t.path_to_root(v)
            tc.assertEqual(t.can_reach(u, v), u in anc_v and u != v, (u, v))
            tc.assertEqual(t.is_ancestor(u, v), u in anc_v and u != v)
            tc.assertEqual(t.is_descendant(v, u), u in anc_v and u != v)


def random_tree(n, seed):
    rnd = random.Random(seed)
    t, ref = DTree("R"), Reference()
    names = ["n0"]
    for i in range(1, n):
        p = rnd.choice(names)
        t.insert(p, f"n{i}")
        ref.insert(p, f"n{i}")
        names.append(f"n{i}")
    return t, ref, rnd


class TestDocumentedExamples(unittest.TestCase):
    def test_readme_usage(self):
        t = DTree("P1")
        t.insert("A", "B")
        t.insert("B", "C")
        self.assertTrue(t.can_reach("A", "C"))
        self.assertEqual(t.path_to_root("C"), ["C", "B", "A"])
        self.assertEqual(t.root_to_path("C"), ["A", "B", "C"])
        self.assertEqual(t.root, "A")
        self.assertIsNone(t.get_parent("A"))
        self.assertEqual(t.depth("A"), 0)
        self.assertEqual(t.source, SOURCE)
        self.assertEqual(t.sink, SINK)

    def test_no_self_reachability(self):
        t = DTree()
        t.insert("A", "B")
        for v in ("A", "B"):
            self.assertFalse(t.can_reach(v, v))
            self.assertTrue(t.can_not_reach(v, v))
            self.assertFalse(t.is_ancestor(v, v))
        self.assertEqual(t.subtree("A"), ["A", "B"])
        self.assertEqual(t.path("A", "A"), ["A"])
        with self.assertRaises(ValueError):
            t.cut_n_paste("B", "B")

    def test_list_level_access(self):
        t = DTree()
        t.insert("A", "B")
        t.insert("A", "C")  # B and C are not connected
        self.assertTrue(t.Q1.is_left_of("B", "C"))
        self.assertTrue(t.Q2.is_left_of("C", "B"))
        self.assertEqual(list(t.Q1), t.q1)

    def test_insert_rules(self):
        t = DTree()
        t.insert("A", "B")
        with self.assertRaises(KeyError):
            t.insert("X", "Y")  # parent must exist
        with self.assertRaises(ValueError):
            t.insert("A", "B")  # child must not exist

    def test_delete_root_disallowed(self):
        t = DTree()
        t.insert("A", "B")
        with self.assertRaises(ValueError):
            t.delete("A")

    def test_two_kinds_of_delete(self):
        def build():
            t = DTree()
            for u, v in [("A", "B"), ("B", "C"), ("B", "D"), ("A", "E")]:
                t.insert(u, v)
            return t
        t = build()
        t.delete("B")  # children move up to A, in B's place
        self.assertEqual(t.children("A"), ["C", "D", "E"])
        self.assertEqual(t.q1, ["A", "C", "D", "E"])
        t = build()
        self.assertEqual(t.delete_subtree("B"), ["B", "C", "D"])
        self.assertEqual(t.q1, ["A", "E"])
        self.assertEqual(t.q2, ["A", "E"])
        with self.assertRaises(ValueError):
            t.delete_subtree("A")

    def test_cut_into_own_subtree_rejected(self):
        t = DTree()
        t.insert("A", "B")
        t.insert("B", "C")
        with self.assertRaises(ValueError):
            t.cut_n_paste("B", "C")

    def test_example_files(self):
        for name in ["Test.csx", "Test1.csx", "test23.csx"]:
            path = os.path.join(EXAMPLES, name)
            if os.path.exists(path):
                t = DTree.from_file(path)
                self.assertEqual(t.root, "01")
                self.assertTrue(t.can_reach("01", "22"))
                self.assertEqual(t.path_to_root("22"), ["22", "10", "06", "04", "01"])


class TestDList(unittest.TestCase):
    def test_list_cs_operations(self):
        from triordinal.dtree import DList
        q = DList("Q")
        self.assertEqual((q.source, q.sink), (SOURCE, SINK))
        q.insert_before("a", SINK)
        q.insert_after("c", "a")
        q.insert_before("b", "c")
        self.assertEqual(q.to_list(), ["a", "b", "c"])
        self.assertEqual(q.to_list(with_markers=True), [SOURCE, "a", "b", "c", SINK])
        self.assertTrue(q.is_left_of("a", "c") and q.is_right_of("c", "a"))
        self.assertTrue(q.is_self_or_left_of("b", "b") and q.is_self_or_right_of("b", "b"))
        self.assertFalse(q.is_left_of("b", "b"))
        self.assertEqual((q.prev("b"), q.next("b")), ("a", "c"))
        self.assertTrue(q.is_allocated("a") and q.is_not_allocated("z"))
        self.assertIsNone(q.index("z"))
        # edge cases of List.cs
        q.insert_before("d", SOURCE)  # redirected to after SOURCE
        q.insert_after("e", SINK)     # redirected to before SINK
        self.assertEqual(q.to_list(), ["d", "a", "b", "c", "e"])
        q.insert_after("a", "a")      # no-op
        q.insert_after("b", "a")      # already there: no-op
        # re-inserting an existing node moves it
        q.insert_after("d", "c")
        self.assertEqual(q.to_list(), ["a", "b", "c", "d", "e"])
        r = DList("R")
        for n in ["a", "b", "c", "d", "e"]:
            r.insert_before(n, SINK)
        self.assertTrue(q.is_same_as(r))
        r.remove("c")
        self.assertFalse(q.is_same_as(r))


class TestVNodes(unittest.TestCase):
    """And/or queries on the topology with constructed nodes (Olgac 2021), checked against brute force."""

    def check_vnodes(self, t, S, vmin=None, vmax=None, umin=None, umax=None):
        vmin = vmin or t.vmin(S)
        vmax = vmax or t.vmax(S)
        umin = umin or t.umin(S)
        umax = umax or t.umax(S)
        for u in t.nodes:
            self.assertEqual(vmin.reaches_all(u), all(t.can_reach(u, v) for v in S), (u, S))
            self.assertEqual(umax.reached_by_all(u), all(t.can_reach(v, u) for v in S), (u, S))
            some = any(t.can_reach(u, v) for v in S)
            self.assertEqual(vmax.reaches_some(u), some, (u, S))
            if some:
                self.assertTrue(vmax.may_reach_some(u), (u, S))  # never rejects a true case
            by_some = any(t.can_reach(v, u) for v in S)
            self.assertEqual(umin.reached_by_some(u), by_some, (u, S))
            if by_some:
                self.assertTrue(umin.may_be_reached_by_some(u), (u, S))

    def test_counterexample_for_reached_by_some(self):
        t = DTree()
        for v in ("a", "m", "b"):
            t.insert("r", v)
        umin = t.umin(["a", "b"])
        self.assertEqual(umin.index_nodes, ("a", "b"))     # (1, 1) from two nodes
        self.assertTrue(umin.may_be_reached_by_some("m"))  # m = (2, 2) passes the filter ...
        self.assertFalse(umin.reached_by_some("m"))        # ... but neither a nor b reaches it

    def test_reached_by_some_with_nested_members(self):
        # s1 is an ancestor of v; s2 lies inside s1's subtree, left of v, and is the last
        # member before v in Q1. Only the topmost members may be searched.
        t = DTree()
        for u, v in [("r", "s1"), ("s1", "s2"), ("s1", "v"), ("r", "w")]:
            t.insert(u, v)
        umin = t.umin(["s2", "s1"])
        self.assertTrue(umin.reached_by_some("v"))
        self.assertTrue(umin.reached_by_some("s2"))
        self.assertFalse(umin.reached_by_some("w"))
        self.assertFalse(umin.reached_by_some("s1"))
        self.check_vnodes(t, ["s2", "s1"])

    def test_counterexample_for_some(self):
        t = DTree()
        for u, v in [("r", "n1"), ("n1", "n2"), ("r", "n3"), ("n2", "n4"),
                     ("n4", "n5"), ("n3", "n6"), ("n3", "n7")]:
            t.insert(u, v)
        up = t.vmax(["n1", "n7"])
        self.assertEqual(up.index_nodes, ("n7", "n1"))  # two different nodes
        self.assertTrue(up.may_reach_some("n6"))          # passes the filter ...
        self.assertFalse(up.reaches_some("n6"))           # ... but reaches neither

    def test_random_sets(self):
        for seed in range(20):
            t, ref, rnd = random_tree(80, seed)
            for k in (1, 2, 3, 8, 25):
                self.check_vnodes(t, rnd.sample(t.nodes, k))

    def test_empty_set(self):
        t = DTree()
        t.insert("a", "b")
        self.assertTrue(t.vmin().reaches_all("a"))
        self.assertTrue(t.umax().reached_by_all("b"))
        self.assertFalse(t.vmax().reaches_some("a"))
        self.assertFalse(t.umin().reached_by_some("b"))

    def test_vnode_survives_changes(self):
        for seed in range(10):
            t, ref, rnd = random_tree(60, seed)
            S = rnd.sample(t.nodes[1:], 5)
            v_s = dict(vmin=t.vmin(S), vmax=t.vmax(S), umin=t.umin(S), umax=t.umax(S))
            n = 60
            for step in range(40):
                r = rnd.random()
                nodes = t.nodes
                if r < 0.5:
                    t.insert(rnd.choice(nodes), f"x{n}")
                    n += 1
                elif r < 0.65:
                    t.delete(rnd.choice(nodes[1:]))
                elif r < 0.75:
                    t.delete_subtree(rnd.choice(nodes[1:]))
                else:
                    u = rnd.choice(nodes[1:])
                    banned = set(t.subtree(u))
                    p = rnd.choice([w for w in nodes if w not in banned])
                    t.cut_n_paste(u, p)
                live = [v for v in S if t.contains(v)]
                self.check_vnodes(t, live, **v_s)
                self.assertEqual(sorted(v_s["umin"].members), sorted(live))

    def test_discard(self):
        # random adds and discards, with inserts, deletes and moves in between
        for seed in range(15):
            t, ref, rnd = random_tree(60, seed)
            v_s = dict(vmin=t.vmin(), vmax=t.vmax(), umin=t.umin(), umax=t.umax())
            S, k = set(), 60
            for step in range(120):
                nodes = t.nodes
                r = rnd.random()
                if r < 0.35:
                    v = rnd.choice(nodes)
                    for x in v_s.values():
                        x.add(v if rnd.random() < 0.5 else t.get_node(v))
                    S.add(v)
                elif r < 0.65 and S:
                    v = rnd.choice(sorted(S))
                    for x in v_s.values():
                        x.discard(v)
                    S.discard(v)
                elif r < 0.8:
                    t.insert(rnd.choice(nodes), f"x{k}")
                    k += 1
                elif r < 0.9 and len(nodes) > 10:
                    v = rnd.choice(nodes[1:])
                    t.delete(v)
                    S.discard(v)
                elif len(nodes) > 10:
                    u = rnd.choice(nodes[1:])
                    banned = set(t.subtree(u))
                    t.cut_n_paste(u, rnd.choice([w for w in nodes if w not in banned]))
                live = sorted(S)
                self.check_vnodes(t, live, **v_s)
                self.assertEqual(sorted(v_s["umin"].members), live)
                for v in live[:3]:
                    self.assertIn(v, v_s["vmax"])
                for v in t.nodes:                        # topmost member that reaches v
                    above = [a for a in t.path_to_root(v)[1:] if a in S]
                    self.assertEqual(v_s["umin"].covering(v), above[-1] if above else None)
        # discarding a non-member is a no-op
        t = DTree()
        t.insert("a", "b")
        u = t.umin(["b"])
        u.discard("a").discard("nobody")
        self.assertEqual(u.members, ["b"])

    def test_next_in_q1(self):
        t, ref, rnd = random_tree(80, 7)
        q1 = t.q1
        for a, b in zip(q1, q1[1:] + [None]):
            self.assertEqual(t.next_in_q1(a), b)
            self.assertEqual(t.next_in_q1(t.get_node(a)), b)

    def test_incremental_add(self):
        t, ref, rnd = random_tree(100, 3)
        v_s = dict(vmin=t.vmin(), vmax=t.vmax(), umin=t.umin(), umax=t.umax())
        S = []
        for v in rnd.sample(t.nodes, 15):
            for x in v_s.values():
                x.add(v)
            S.append(v)
            self.check_vnodes(t, S, **v_s)


class TestNodeHandles(unittest.TestCase):
    """Handles refer directly to a node's positions; names keep working."""

    def test_handles(self):
        t = DTree()
        b = t.insert("A", "B")
        c = t.insert(b, "C")
        d = t.insert("A", "D")
        a = t.get_node("A")
        self.assertIsInstance(b, DNode)
        self.assertEqual(b.name, "B")
        self.assertTrue(t.can_reach(a, c) and t.can_reach(b, c) and t.can_reach("A", c))
        self.assertFalse(t.can_reach(c, a) or t.can_reach(b, d) or t.can_reach(c, c))
        self.assertTrue(t.is_root(a) and not t.is_root(b))
        self.assertEqual(t.depth(c), 2)
        self.assertIs(c.parent, b)
        self.assertIsNone(a.parent)
        self.assertEqual([k.name for k in a.children], ["B", "D"])
        self.assertIs(t.try_get_node("D"), d)
        self.assertIsNone(t.try_get_node("X"))
        t.cut_n_paste(c, d)
        self.assertTrue(t.can_reach(d, c) and not t.can_reach(b, c))
        self.assertTrue(t.can_reach(t.get_node("A"), t.get_node("C")))  # handles stay valid after a move
        t.delete(b)
        self.assertFalse(b.is_in_tree or t.can_reach(a, b))
        with self.assertRaises(KeyError):
            t.insert(b, "E")
        other = DTree("other")
        x = other.insert("X", "Y")
        self.assertFalse(t.can_reach(a, x))
        with self.assertRaises(KeyError):
            t.delete(x)
        self.assertEqual(t.delete_subtree(d), ["D", "C"])
        self.assertFalse(c.is_in_tree)
        self.assertEqual(t.size, 1)

    def test_and_or_queries_accept_handles(self):
        t = DTree()
        b = t.insert("A", "B")
        c = t.insert(b, "C")
        d = t.insert("A", "D")
        a = t.get_node("A")
        self.assertTrue(t.vmin([c, d]).reaches_all(a))
        self.assertFalse(t.vmin([c, "D"]).reaches_all(b))
        self.assertTrue(t.vmax([c, d]).reaches_some(b))
        self.assertTrue(t.umax([a, b]).reached_by_all(c))
        self.assertTrue(t.umin([b, d]).reached_by_some(c))


class TestSubtreeEnd(unittest.TestCase):
    """The end of a subtree in Q1, marked by the closing cell of its root."""

    @staticmethod
    def _ref_last(t, v):
        w = v
        while t.children(w):
            w = t.children(w)[-1]
        return w

    def test_top_down_comb(self):
        # a chain, then new leaves under the spine nodes from the top down: the plain walk
        # would be O(depth) per insertion here
        t, ref = DTree(), Reference()
        d = 300
        names = ["n0"]
        for i in range(1, d):
            t.insert(names[-1], f"n{i}")
            ref.insert(names[-1], f"n{i}")
            names.append(f"n{i}")
        k = d
        for rnd_ in range(3):
            for i in range(d):
                t.insert(f"n{i}", f"x{k}")
                ref.insert(f"n{i}", f"x{k}")
                k += 1
        check(self, t, ref)
        for v in random.Random(1).sample(t.nodes, 50):
            self.assertEqual(t.subtree_last(v), self._ref_last(t, v))

    def test_inserts_mixed_with_deletes_and_moves(self):
        self._mixed()

    def _mixed(self):
        for seed in range(25):
            t, ref, rnd = random_tree(40, seed)
            k = 40
            for step in range(150):
                nodes = ref.nodes()
                inner = [v for v in nodes if v != ref.root]
                r = rnd.random()
                if r < 0.55 or len(inner) < 8:
                    # favor deep parents and the spine of last children
                    p = rnd.choice(nodes) if rnd.random() < 0.5 else self._ref_last(t, rnd.choice(nodes))
                    if rnd.random() < 0.3:
                        p = ref.root
                    t.insert(p, f"x{k}")
                    ref.insert(p, f"x{k}")
                    k += 1
                elif r < 0.7:
                    v = rnd.choice(inner)
                    t.delete(v)
                    ref.delete(v)
                elif r < 0.8:
                    v = rnd.choice(inner)
                    t.delete_subtree(v)
                    ref.delete_subtree(v)
                else:
                    u = rnd.choice(inner)
                    banned = set(t.subtree(u))
                    p = rnd.choice([w for w in nodes if w not in banned])
                    t.cut_n_paste(u, p)
                    ref.move(u, p)
                if step % 10 == 0:
                    for v in rnd.sample(ref.nodes(), min(10, len(ref.nodes()))):
                        self.assertEqual(t.subtree_last(v), self._ref_last(t, v))
            check(self, t, ref)


class TestAgainstReference(unittest.TestCase):
    def test_random_inserts(self):
        for seed in range(30):
            t, ref, _ = random_tree(60, seed)
            check(self, t, ref)

    def test_random_deletes_and_moves(self):
        for seed in range(30):
            t, ref, rnd = random_tree(80, seed)
            for _ in range(40):
                nodes = [n for n in ref.nodes() if n != ref.root]
                if len(nodes) < 10:
                    break
                r = rnd.random()
                if r < 0.35:
                    v = rnd.choice(nodes)
                    t.delete(v)
                    ref.delete(v)
                elif r < 0.5:
                    v = rnd.choice(nodes)
                    expected = t.subtree(v)
                    self.assertEqual(t.delete_subtree(v), expected)
                    ref.delete_subtree(v)
                    for n in expected:
                        self.assertFalse(t.contains(n))
                else:
                    u = rnd.choice(nodes)
                    banned = set(t.subtree(u))
                    targets = [n for n in ref.nodes() if n not in banned]
                    p = rnd.choice(targets)
                    t.cut_n_paste(u, p)
                    ref.move(u, p)
                check(self, t, ref)


class TestSiblingInsert(unittest.TestCase):
    def test_example(self):
        t = DTree()
        t.insert("A", "B")
        t.insert("A", "D")
        t.insert("B", "C")
        t.insert_after("B", "X")       # A: B, X, D
        t.insert_before("B", "W")      # A: W, B, X, D
        t.insert_before("C", "C0")     # B: C0, C
        self.assertEqual(t.children("A"), ["W", "B", "X", "D"])
        self.assertEqual(t.children("B"), ["C0", "C"])
        self.assertEqual(t.q1, ["A", "W", "B", "C0", "C", "X", "D"])
        self.assertEqual(t.q2, ["A", "D", "X", "B", "C", "C0", "W"])
        self.assertTrue(t.can_reach("A", "X") and not t.can_reach("B", "X"))
        self.assertEqual(t.subtree_last("A"), "D")

    def test_rules(self):
        t = DTree()
        t.insert("A", "B")
        with self.assertRaises(ValueError):
            t.insert_after("A", "Z")           # the root has no siblings
        with self.assertRaises(ValueError):
            t.insert_before("A", "Z")
        with self.assertRaises(ValueError):
            t.insert_after("B", "A")           # already in the tree
        with self.assertRaises(KeyError):
            t.insert_after("nobody", "Z")
        n = t.insert_after(t.get_node("B"), "C")   # handles work too
        self.assertIsInstance(n, DNode)
        self.assertEqual(t.children("A"), ["B", "C"])

    def test_example_file(self):
        t = DTree.from_file(os.path.join(EXAMPLES, "siblings.csx"))
        self.assertEqual(t.children("01"), ["02", "04", "06", "05"])
        self.assertEqual(t.q1, ["01", "02", "03a", "03", "04", "06", "05"])
        self.assertEqual(t.q2, ["01", "05", "06", "04", "02", "03", "03a"])

    def test_description_lines(self):
        t = DTree()
        t.add_line("A: B; D")
        t.add_line("B > X; Y")         # X after B, Y after X
        t.add_line("D < W1; W2")       # W1 before D, W2 before D
        t.add_line("B: C")
        self.assertEqual(t.children("A"), ["B", "X", "Y", "W1", "W2", "D"])
        self.assertEqual(t.children("B"), ["C"])

    def test_random_mix(self):
        # all three kinds of insertion, mixed with deletes and moves, against the reference
        for seed in range(12):
            t, ref, rnd = random_tree(20, seed)
            k = 0
            for _ in range(100):
                nodes = ref.nodes()
                inner = [n for n in nodes if n != ref.root]
                r = rnd.random()
                name = f"x{k}"
                if r < 0.25:
                    p = rnd.choice(nodes)
                    t.insert(p, name)
                    ref.insert(p, name)
                    k += 1
                elif r < 0.5 and inner:
                    s = rnd.choice(inner)
                    t.insert_after(s, name)
                    ref.insert_after(s, name)
                    k += 1
                elif r < 0.75 and inner:
                    s = rnd.choice(inner)
                    t.insert_before(s, name)
                    ref.insert_before(s, name)
                    k += 1
                elif r < 0.85 and len(inner) > 10:
                    v = rnd.choice(inner)
                    t.delete(v)
                    ref.delete(v)
                elif len(inner) > 10:
                    u = rnd.choice(inner)
                    banned = set(t.subtree(u))
                    p = rnd.choice([n for n in nodes if n not in banned])
                    t.cut_n_paste(u, p)
                    ref.move(u, p)
                check(self, t, ref)
                for v in rnd.sample(ref.nodes(), 3):
                    sub_v = [w for w in ref.nodes() if w == v or v == ref.root or v in ref_ancestors(ref.parent, w)]
                    self.assertEqual(t.subtree_last(v), [w for w in t.q1 if w in sub_v][-1])

    def test_same_gap_many_times(self):
        # repeated insertion into the same gap from both sides: positions stay strictly increasing
        t, ref = DTree(), Reference()
        t.insert("r", "a")
        ref.insert("r", "a")
        t.insert("r", "b")
        ref.insert("r", "b")
        left, right = "a", "b"
        for i in range(400):
            if i % 2:
                t.insert_after(left, f"l{i}")
                ref.insert_after(left, f"l{i}")
                left = f"l{i}"
            else:
                t.insert_before(right, f"r{i}")
                ref.insert_before(right, f"r{i}")
                right = f"r{i}"
        check(self, t, ref)

    def test_constructed_nodes_stay_valid(self):
        t, ref, rnd = random_tree(60, 3)
        S = rnd.sample(ref.nodes(), 6)
        um, vm = t.umin(S), t.vmax(S)
        for i in range(60):
            s = rnd.choice([n for n in ref.nodes() if n != ref.root])
            if i % 2:
                t.insert_after(s, f"y{i}")
                ref.insert_after(s, f"y{i}")
            else:
                t.insert_before(s, f"y{i}")
                ref.insert_before(s, f"y{i}")
        for v in ref.nodes():
            anc = set(ref_ancestors(ref.parent, v)[1:]) | ({ref.root} if v != ref.root else set())
            self.assertEqual(um.reached_by_some(v), any(m in anc for m in S), v)
            below = {w for w in ref.nodes() if w != v and (v == ref.root or v in ref_ancestors(ref.parent, w))}
            self.assertEqual(vm.reaches_some(v), any(m in below for m in S), v)


class TestNoSizeLimit(unittest.TestCase):
    def test_deep_chain(self):
        t = DTree()
        for i in range(5000):
            t.insert(f"v{i}", f"v{i + 1}")
        self.assertEqual(t.depth("v5000"), 5000)
        self.assertTrue(t.can_reach("v0", "v5000"))
        self.assertFalse(t.can_reach("v5000", "v0"))
        # a chain nests every new node into the gap of its parent: renumbering keeps the
        # positions strictly increasing and the denominators bounded
        self.assertTrue(labels_strictly_increase(t._q1) and labels_strictly_increase(t._q2))
        self.assertTrue(all(c.den.bit_length() <= 64 for q in (t._q1, t._q2) for c in cells(q)))

    def test_wide_node(self):
        t = DTree()
        for i in range(5000):
            t.insert("r", f"c{i}")
        self.assertEqual(t.subtree_size("r"), 5001)
        self.assertFalse(t.can_reach("c1", "c2"))
        self.assertEqual(t.q2[:3], ["r", "c4999", "c4998"])
        self.assertTrue(labels_strictly_increase(t._q2))

    def test_growth_at_both_ends(self):
        from triordinal.dtree import DList
        q = DList("Q")
        for i in range(5000):
            q.insert_before(f"r{i}", SINK)   # grow to the right
            q.insert_after(f"l{i}", SOURCE)  # grow to the left
        self.assertTrue(labels_strictly_increase(q))
        self.assertEqual(q.to_list()[:2], ["l4999", "l4998"])
        self.assertEqual(q.to_list()[-2:], ["r4998", "r4999"])

    def test_star_needs_no_renumbering(self):
        t = DTree()
        t.insert("r", "x")
        t.insert("r", "y")
        for i in range(5000):
            t.insert("x", f"c{i}")  # star under an inner node: same gap every time
        self.assertEqual((t.Q1.renumber_count, t.Q2.renumber_count), (0, 0))
        self.assertTrue(t.can_reach("x", "c4999"))
        self.assertFalse(t.can_reach("c0", "c1"))

    def test_alternating_worst_case(self):
        # always insert into the newer half of the last gap, alternating sides:
        # mediant denominators grow like Fibonacci numbers and force renumbering
        t = DTree()
        left = "n0"
        for i in range(1, 4000):
            t.insert(left, f"n{i}")
            if i % 2 == 0:
                left = f"n{i}"
        self.assertGreater(t.Q2.renumber_count, 0)
        self.assertTrue(labels_strictly_increase(t._q1))
        self.assertTrue(labels_strictly_increase(t._q2))
        for q in (t._q1, t._q2):
            self.assertTrue(all(c.den.bit_length() <= 64 for c in cells(q)))

    def test_random_list_operations(self):
        from triordinal.dtree import DList
        rnd = random.Random(7)
        q, ref = DList("Q"), []
        for i in range(20000):
            r = rnd.random()
            if ref and r < 0.15:
                v = rnd.choice(ref)
                q.remove(v)
                ref.remove(v)
                continue
            name = f"v{i}"
            if not ref or r < 0.25:
                q.insert_after(name, SOURCE)
                ref.insert(0, name)
            else:
                # hammer a few hot spots to force renumbering
                j = rnd.choice([0, len(ref) // 2, len(ref) - 1, rnd.randrange(len(ref))])
                if rnd.random() < 0.5:
                    q.insert_after(name, ref[j])
                    ref.insert(j + 1, name)
                else:
                    q.insert_before(name, ref[j])
                    ref.insert(j, name)
        self.assertEqual(q.to_list(), ref)
        self.assertTrue(labels_strictly_increase(q))

    def test_adversarial_gaps(self):
        # alternate between the two most crowded gaps in Q2 and Q1
        t = DTree()
        t.insert("r", "a")
        for i in range(3000):
            t.insert("r", f"x{i}")
            t.insert("a", f"y{i}")
        self.assertTrue(labels_strictly_increase(t._q1))
        self.assertTrue(labels_strictly_increase(t._q2))
        self.assertTrue(t.can_reach("a", "y2999"))
        self.assertFalse(t.can_reach("x0", "y0"))


def snapshot(t):
    """Everything an operation could change: both lists cell by cell, positions, parents, names."""
    pos = [[(c.name, c.num, c.den) for c in cells(q)] for q in (t._q1, t._q2)]
    return (raw_cells(t._q1), raw_cells(t._q2), pos, t._parent, sorted(t._nodes), t.root,
            {n.name: [k.name for k in (n.kids or ())] for n in t._nodes.values()})


class TestReviewPatterns(unittest.TestCase):
    """The complexity patterns of Onur Safi's review of DTree 1.8.0, checked for correctness;
    their cost is measured by the benchmarks (python -m triordinal.dtree.bench --review)."""

    def test_extend_bottom_then_child_near_top(self):
        # a deep branch is extended at the bottom, then a child is added near its top
        t, ref = DTree(), Reference()
        d = 1500
        t.insert("r", "c0")
        ref.insert("r", "c0")
        for i in range(1, d):
            t.insert(f"c{i - 1}", f"c{i}")
            ref.insert(f"c{i - 1}", f"c{i}")
        bottom = f"c{d - 1}"
        for r in range(300):
            t.insert(bottom, f"b{r}")
            ref.insert(bottom, f"b{r}")
            bottom = f"b{r}"
            t.insert(f"c{r}", f"y{r}")
            ref.insert(f"c{r}", f"y{r}")
        check(self, t, ref)
        self.assertEqual(t.subtree_last("c0"), "y0")
        self.assertEqual(t.subtree_last("c1"), "y1")

    def test_insert_before_first_child_deep(self):
        t, ref = DTree(), Reference()
        d = 1500
        t.insert("r", "c0")
        ref.insert("r", "c0")
        for i in range(1, d):
            t.insert(f"c{i - 1}", f"c{i}")
            ref.insert(f"c{i - 1}", f"c{i}")
        for i in range(0, d, 7):
            t.insert_before(f"c{i}", f"w{i}")      # c{i} is the first child of its parent
            ref.insert_before(f"c{i}", f"w{i}")
        check(self, t, ref)

    def test_delete_subtree_and_move_deep(self):
        t, ref = DTree(), Reference()
        d = 1500
        t.insert("r", "c0")
        ref.insert("r", "c0")
        for i in range(1, d):
            t.insert(f"c{i - 1}", f"c{i}")
            ref.insert(f"c{i - 1}", f"c{i}")
        t.insert("r", "s")
        ref.insert("r", "s")
        for i in range(d - 10, 10, -97):
            t.cut_n_paste(f"c{i}", "s")
            ref.move(f"c{i}", "s")
            check(self, t, ref)
        self.assertEqual(t.delete_subtree("c5"), ref_preorder(ref.children, "c5"))
        ref.delete_subtree("c5")
        check(self, t, ref)

    def test_many_siblings(self):
        t, ref = DTree(), Reference()
        t.insert("r", "p")
        ref.insert("r", "p")
        for i in range(300):
            t.insert("p", f"k{i}")
            ref.insert("p", f"k{i}")
        for i in range(0, 300, 3):
            t.insert_after(f"k{i}", f"a{i}")
            ref.insert_after(f"k{i}", f"a{i}")
            t.insert_before(f"k{i}", f"b{i}")
            ref.insert_before(f"k{i}", f"b{i}")
        for i in range(299, -1, -2):
            t.delete(f"k{i}")
            ref.delete(f"k{i}")
        check(self, t, ref)

    def test_closing_cells_come_and_go(self):
        t = DTree()
        t.insert("A", "B")
        self.assertEqual(raw_cells(t._q1), ["A", "B", ")A"])
        t.insert("B", "C")
        self.assertEqual(raw_cells(t._q1), ["A", "B", "C", ")B", ")A"])
        self.assertEqual(raw_cells(t._q2), ["A", "B", "C", ")B", ")A"])
        t.delete("C")                                    # B has no children left
        self.assertEqual(raw_cells(t._q1), ["A", "B", ")A"])
        t.delete_subtree("B")
        self.assertEqual(raw_cells(t._q1), ["A"])
        self.assertEqual(raw_cells(t._q2), ["A"])
        t.insert("A", "B")
        t.insert("A", "C")
        t.cut_n_paste("C", "B")
        self.assertEqual(raw_cells(t._q1), ["A", "B", "C", ")B", ")A"])


class TestNoPartialState(unittest.TestCase):
    """An operation that raises leaves the tree exactly as it was."""

    def test_first_insert(self):
        for args, exc in ((("A", "A"), ValueError), (("A", None), TypeError), (("A", ""), ValueError),
                          (("", "B"), ValueError), ((None, "B"), TypeError), (("A", SINK), ValueError),
                          ((SOURCE, "B"), ValueError)):
            t = DTree()
            with self.assertRaises(exc, msg=args):
                t.insert(*args)
            self.assertEqual((t.size, t.root, t.q1, t.q2, len(t.Q1)), (0, None, [], [], 0), args)
            self.assertEqual(raw_cells(t._q1), [])
            t.insert("A", "B")                         # the tree is still usable
            self.assertEqual(t.q1, ["A", "B"])

    def test_failing_operations(self):
        t, ref, rnd = random_tree(30, 4)
        t.insert_after("n1", "s1")
        other = DTree("other").insert("X", "Y")
        gone = t.insert("n3", "gone")
        t.delete(gone)
        failing = [
            (lambda: t.insert("nobody", "z"), KeyError),
            (lambda: t.insert("n2", "n5"), ValueError),
            (lambda: t.insert("n2", None), TypeError),
            (lambda: t.insert("n2", ""), ValueError),
            (lambda: t.insert(gone, "z"), KeyError),
            (lambda: t.insert(other, "z"), KeyError),
            (lambda: t.insert_after("n0", "z"), ValueError),
            (lambda: t.insert_before("n0", "z"), ValueError),
            (lambda: t.insert_after("n1", "n2"), ValueError),
            (lambda: t.insert_before("nobody", "z"), KeyError),
            (lambda: t.delete("n0"), ValueError),
            (lambda: t.delete("nobody"), KeyError),
            (lambda: t.delete(gone), KeyError),
            (lambda: t.delete_subtree("n0"), ValueError),
            (lambda: t.cut_n_paste("n0", "n1"), ValueError),
            (lambda: t.cut_n_paste("n1", "n1"), ValueError),
            (lambda: t.cut_n_paste("n0", "nobody"), KeyError),
            (lambda: t.add_line("no operator here"), ValueError),
        ]
        sub = t.subtree("n1")
        if len(sub) > 1:
            failing.append((lambda: t.cut_n_paste("n1", sub[-1]), ValueError))
        for op, exc in failing:
            before = snapshot(t)
            with self.assertRaises(exc):
                op()
            self.assertEqual(snapshot(t), before)

    def test_from_file_rejects_lines_without_operator(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csx", delete=False, encoding="utf-8") as fh:
            fh.write("A: B\njust text\nB: C\n")
        try:
            with self.assertRaises(ValueError):
                DTree.from_file(fh.name)
        finally:
            os.remove(fh.name)


class TestReadOnlyProjections(unittest.TestCase):
    def test_no_way_to_change_the_tree(self):
        t = DTree()
        t.insert("A", "B")
        t.insert("B", "C")
        t.insert("A", "D")
        for q in (t.Q1, t.Q2):
            for name in ("insert_after", "insert_before", "remove", "cut_block", "paste_block_after"):
                self.assertFalse(hasattr(q, name), name)
        with self.assertRaises(AttributeError):
            t.Q1.list = None                          # no attributes can be added either

    def test_list_level_reads(self):
        t = DTree()
        t.insert("A", "B")
        t.insert("B", "C")
        t.insert("A", "D")
        q1, q2 = t.Q1, t.Q2
        self.assertEqual((list(q1), q1.to_list(True), len(q1)), (["A", "B", "C", "D"], [SOURCE, "A", "B", "C", "D", SINK], 4))
        self.assertEqual(list(q2), ["A", "D", "B", "C"])
        self.assertEqual((q1.next("C"), q1.prev("D"), q1.next("D"), q1.prev("A")), ("D", "C", SINK, SOURCE))
        self.assertTrue(q1.is_left_of("C", "D") and q1.precedes("A", "C") and q1.is_right_of("D", "C"))
        self.assertTrue(q1.is_self_or_left_of("B", "B") and q1.is_self_or_right_of("B", "B"))
        self.assertTrue("C" in q1 and "Z" not in q1 and q1.is_allocated("C") and q1.is_not_allocated("Z"))
        self.assertLess(q1.index("C"), q1.index("D"))
        self.assertIsNone(q1.index("Z"))
        self.assertEqual((q1.source, q1.sink, q1.name), (SOURCE, SINK, "P1.Q1"))
        self.assertTrue(q1.is_same_as(t.Q1) and not q1.is_same_as(q2))
        self.assertEqual(repr(q1), "P1.Q1: [A, B, C, D]")
        self.assertIs(t.Q1, q1)                       # one live view per list
        t.insert("C", "E")
        self.assertEqual(list(q1), ["A", "B", "C", "E", "D"])


class TestStrict(unittest.TestCase):
    def build(self, strict):
        t = DTree(strict=strict)
        t.insert("A", "B")
        t.insert("B", "C")
        gone = t.insert("A", "X")
        t.delete(gone)
        return t, gone

    def test_lenient_default(self):
        t, gone = self.build(False)
        self.assertFalse(t.strict)
        self.assertFalse(t.can_reach("A", "Bx") or t.can_reach("Bx", "A") or t.can_reach(gone, "A"))
        self.assertTrue(t.can_not_reach("A", "Bx"))
        self.assertFalse(t.is_root("nobody") or t.is_root(None))
        self.assertFalse(t.vmin(["C"]).reaches_all("nobody"))
        self.assertIsNone(t.umin(["B"]).covering("nobody"))

    def test_strict_raises(self):
        t, gone = self.build(True)
        self.assertTrue(t.strict)
        self.assertTrue(t.can_reach("A", "C") and not t.can_reach("C", "A"))
        calls = [lambda: t.can_reach("A", "Bx"), lambda: t.can_reach("Bx", "A"),
                 lambda: t.can_reach(gone, "A"), lambda: t.can_reach("A", gone),
                 lambda: t.can_not_reach("A", "Bx"), lambda: t.is_ancestor("A", "Bx"),
                 lambda: t.is_descendant("Bx", "A"), lambda: t.is_root("nobody"), lambda: t.is_root(None)]
        S = ["C"]
        for s in (t.vmin(S), t.vmax(S), t.umin(S), t.umax(S)):
            for name in ("reaches_all", "may_reach_some", "reaches_some", "reached_by_all",
                         "may_be_reached_by_some", "reached_by_some", "covering"):
                if hasattr(s, name):
                    calls.append(lambda f=getattr(s, name): f("nobody"))
        for call in calls:
            with self.assertRaises(KeyError):
                call()
        # membership tests never raise
        self.assertFalse(t.contains("nobody") or "nobody" in t or t.same_subtree("A", "nobody"))
        self.assertFalse("nobody" in t.umin(S))
        t.umin(S).discard("nobody")

    def test_from_file_strict(self):
        t = DTree.from_file(os.path.join(EXAMPLES, "siblings.csx"), strict=True)
        with self.assertRaises(KeyError):
            t.can_reach("01", "nobody")


class TestMembersAreNodes(unittest.TestCase):
    def test_reused_name_is_not_a_member(self):
        # a member that was deleted stays out, even when a new node gets its name
        t = DTree()
        t.insert("r", "X")
        t.insert("r", "Y")
        S = dict(vmin=t.vmin(["X"]), vmax=t.vmax(["X"]), umin=t.umin(["X"]), umax=t.umax(["X"]))
        t.delete("X")
        t.insert("Y", "X")                     # new and unrelated
        for s in S.values():
            self.assertEqual(s.members, [])
            self.assertNotIn("X", s)
        self.assertFalse(S["vmax"].reaches_some("r"))
        self.assertFalse(S["umin"].reached_by_some("X"))
        self.assertTrue(S["vmin"].reaches_all("r"))   # empty set

    def test_handles_and_names_are_one_member(self):
        t = DTree()
        b = t.insert("A", "B")
        u = t.umin(["B"]).add(b)
        self.assertEqual(len(u), 1)
        self.assertIn(b, u)
        u.discard("B")
        self.assertEqual(u.members, [])


class TestIsRoot(unittest.TestCase):
    def test_empty_tree(self):
        t = DTree()
        self.assertFalse(t.is_root(None) or t.is_root("A"))
        t.insert("A", "B")
        self.assertTrue(t.is_root("A") and t.is_root(t.get_node("A")))
        self.assertFalse(t.is_root("B") or t.is_root(None))


if __name__ == "__main__":
    unittest.main()
