"""Tests for DList on its own: order, precedence and renumbering against a plain Python list."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triordinal.dlist import POSITIONS, SINK, SOURCE, DList, _LIMIT  # noqa: E402


class TestDList(unittest.TestCase):
    POSITIONS = "rational"

    def make(self, name):
        return DList(name, self.POSITIONS)
    def check(self, q, ref):
        self.assertEqual(list(q), ref)
        for _ in range(200):
            a, b = random.sample(ref, 2) if len(ref) > 1 else (ref[0], ref[0])
            self.assertEqual(q.precedes(a, b), ref.index(a) < ref.index(b))

    def test_random_inserts_and_removes(self):
        rnd = random.Random(1)
        q, ref = self.make("Q"), []
        for i in range(3000):
            name = f"n{i}"
            if ref and rnd.random() < 0.2:
                victim = rnd.choice(ref)
                q.remove(victim)
                ref.remove(victim)
                continue
            if not ref or rnd.random() < 0.5:
                anchor = rnd.choice([SOURCE] + ref)
                q.insert_after(name, anchor)
                ref.insert(0 if anchor == SOURCE else ref.index(anchor) + 1, name)
            else:
                anchor = rnd.choice(ref + [SINK])
                q.insert_before(name, anchor)
                ref.insert(len(ref) if anchor == SINK else ref.index(anchor), name)
        self.check(q, ref)

    def test_alternating_worst_case_renumbers_and_keeps_order(self):
        q, ref = self.make("Q"), ["a", "b"]
        q.insert_after("a", SOURCE)
        q.insert_after("b", "a")
        left, right = "a", "b"
        for i in range(3000):
            name = f"x{i}"
            q.insert_after(name, left)
            ref.insert(ref.index(left) + 1, name)
            left, right = (name, right) if i % 2 else (left, name)
        self.assertGreater(q.renumber_count, 0)
        self.check(q, ref)

    def test_markers_cannot_be_inserted_moved_or_removed(self):
        q = self.make("Q")
        q.insert_after("a", SOURCE)
        for f in (lambda: q.insert_before(SINK, "a"), lambda: q.insert_after(SOURCE, "a"),
                  lambda: q.insert_after(SINK, "a"), lambda: q.insert_before(SOURCE, "a"),
                  lambda: q.remove(SOURCE), lambda: q.remove(SINK)):
            with self.assertRaises(ValueError):
                f()
        self.assertEqual(q.to_list(with_markers=True), [SOURCE, "a", SINK])

    def test_many_end_insertions_then_one_gap(self):
        # the reviewer's pattern: values grow with every insertion at the end, then one gap
        # is filled alternately; Python's integers do not overflow, the order must hold
        q = self.make("Q")
        q.insert_after("r", SOURCE)
        prev = None
        for i in range(200_000):
            q.insert_before(f"c{i}", SINK)
            if prev:
                q.remove(prev)
            prev = f"c{i}"
        left, right, ref = "r", prev, ["r", prev]
        for i in range(300):
            name = f"s{i}"
            q.insert_after(name, left)
            ref.insert(ref.index(left) + 1, name)
            left, right = (name, right) if i % 2 else (left, name)
        self.check(q, ref)


class TestUnnamedCells(unittest.TestCase):
    """Unnamed cells (DTree's closing cells) hold a position but are passed over by name."""

    POSITIONS = "rational"

    def make(self, name):
        return DList(name, self.POSITIONS)

    def test_unnamed_cells_are_invisible_by_name(self):
        q = self.make("Q")
        for n in "abc":
            q.insert_before(n, SINK)
        a = q._cells["a"]
        u1 = q._insert_cell_after(None, a)          # a, u1, b, c
        u2 = q._insert_cell_after(None, u1)         # a, u1, u2, b, c
        self.assertEqual(list(q), ["a", "b", "c"])
        self.assertEqual(len(q), 3)
        self.assertEqual((q.next("a"), q.prev("b")), ("b", "a"))
        self.assertTrue(DList._lt(a, u1) and DList._lt(u1, u2) and DList._lt(u2, q._cells["b"]))
        q.insert_after("x", "a")                    # directly after a, before the unnamed cells
        self.assertEqual(q.next("x"), "b")
        self.assertIs(q._cells["x"].next, u1)
        self.assertEqual(q.cut_block("x", "b"), ["x", "b"])   # unnamed cells inside go too
        self.assertEqual(list(q), ["a", "c"])
        self.assertEqual(q.next("a"), "c")

    def test_cell_level_move_keeps_cells(self):
        q = self.make("Q")
        for n in "abcde":
            q.insert_before(n, SINK)
        b, d = q._cells["b"], q._cells["d"]
        block = q._cut_cells(b, d, forget=False)
        self.assertEqual([c.name for c in block], ["b", "c", "d"])
        q._paste_cells_after(block, q._cells["e"])
        self.assertEqual(list(q), ["a", "e", "b", "c", "d"])
        self.assertIs(q._cells["c"], block[1])
        with self.assertRaises(ValueError):
            q._insert_cell_after("a", q.first)       # names stay unique
        with self.assertRaises(ValueError):
            q._insert_cell_after(None, q.last)       # nothing follows SINK
        with self.assertRaises(ValueError):
            q.cut_block(SOURCE, "a")                 # markers cannot be cut


class TestPasteAndLimits(unittest.TestCase):
    """2.3.0: a pasted block is placed as a whole; rational positions renumber only when a
    mediant cannot be stored."""

    def increasing(self, q):
        c = q.first
        while c.next is not None:
            if not q._lt(c, c.next):
                return False
            c = c.next
        return True

    def build(self, positions, n=40):
        q = DList("Q", positions)
        for i in range(n):
            q.insert_before(f"v{i}", SINK)
        return q

    def move(self, q, first, last, anchor):
        block = q._cut_cells(q._cells[first], q._cells[last], forget=False)
        q._paste_cells_after(block, q._cells[anchor])
        return block

    def test_random_moves_keep_order(self):
        for positions in POSITIONS:
            rnd = random.Random(4)
            q, ref = self.build(positions, 300), [f"v{i}" for i in range(300)]
            for _ in range(2000):
                i = rnd.randrange(len(ref))
                j = min(len(ref) - 1, i + rnd.choice([0, 0, 1, 3, 20]))
                block = ref[i:j + 1]
                rest = ref[:i] + ref[j + 1:]
                k = rnd.randrange(len(rest) + 1)                # paste after rest[k - 1], or after SOURCE
                anchor = q.first if k == 0 else q._cells[rest[k - 1]]
                q._paste_cells_after(q._cut_cells(q._cells[block[0]], q._cells[block[-1]], forget=False), anchor)
                ref = rest[:k] + block + rest[k:]
                self.assertTrue(self.increasing(q), positions)
            self.assertEqual(list(q), ref, positions)
            self.assertGreater(q.paste_count, 0, positions)
            for _ in range(300):
                a, b = rnd.sample(ref, 2)
                self.assertEqual(q.precedes(a, b), ref.index(a) < ref.index(b))

    def test_integer_block_is_shifted_when_its_span_fits(self):
        q = self.build("integer", 10)                           # appends halve the gap to SINK each time
        inner = [q.index(f"v{i}") for i in (7, 8, 9)]
        self.move(q, "v7", "v9", "v0")                          # the gap from v0 to v1 is the widest
        moved = [q.index(f"v{i}") for i in (7, 8, 9)]
        self.assertEqual([b - a for a, b in zip(inner, inner[1:])], [b - a for a, b in zip(moved, moved[1:])])
        self.assertTrue(q.index("v0") < moved[0] and moved[-1] < q.index("v1"))
        self.assertEqual((q.paste_count, q.renumber_count), (1, 0))

    def test_integer_block_is_spread_or_renumbered(self):
        q = DList("Q", "integer")
        for n in "abcdef":
            q.insert_before(n, SINK)
        a, b = q._cells["a"], q._cells["b"]
        b.num = a.num + 4                                       # leave three free labels after a
        self.move(q, "c", "e", "a")                             # span too wide, three cells: spread
        self.assertEqual(list(q), ["a", "c", "d", "e", "b", "f"])
        self.assertEqual([q.index(n) - q.index("a") for n in "cde"], [1, 2, 3])
        self.assertEqual((q.paste_count, q.renumber_count), (1, 0))
        self.move(q, "e", "b", "a")                             # no room for two more: renumber
        self.assertEqual(list(q), ["a", "e", "b", "c", "d", "f"])
        self.assertTrue(self.increasing(q))
        self.assertEqual((q.paste_count, q.renumber_count), (1, 1))

    def test_rational_block_gets_the_chain_of_mediants(self):
        q = self.build("rational", 6)
        self.move(q, "v1", "v3", "v4")
        a, c = q._cells["v4"], q._cells["v5"]
        for j, n in enumerate(["v1", "v2", "v3"], 1):
            x = q._cells[n]
            self.assertEqual((x.num, x.den), (a.num + j * c.num, a.den + j * c.den))
        self.assertEqual((q.paste_count, q.renumber_count), (1, 0))

    def test_rational_renumbers_only_when_a_mediant_cannot_be_stored(self):
        q = DList("Q")
        q.insert_before("a", SINK)
        q.insert_before("b", SINK)
        a, b = q._cells["a"], q._cells["b"]
        a.num, a.den = 1, _LIMIT                                # stored, but a mediant with b would exceed _LIMIT
        b.num, b.den = 1, 1
        q.insert_after("x", "b")                                # elsewhere: stored, nothing renumbered
        self.assertEqual(q.renumber_count, 0)
        q.insert_after("y", "a")
        self.assertEqual(q.renumber_count, 1)
        self.assertEqual(list(q), ["a", "y", "b", "x"])
        self.assertTrue(self.increasing(q))
        self.assertTrue(all(c.den <= _LIMIT for c in (a, b, q._cells["y"])))

    def test_alternating_denominators_reach_the_limit_before_renumbering(self):
        q = DList("Q")
        q.insert_before("L", SINK)
        q.insert_before("R", SINK)
        left, right, top = "L", "R", 0
        for i in range(200):
            q.insert_after(f"x{i}", left)
            if i % 2:
                left = f"x{i}"
            else:
                right = f"x{i}"
            top = max(top, q._cells[f"x{i}"].den)
            if q.renumber_count:
                break
        self.assertEqual(q.renumber_count, 1)
        self.assertGreater(top, _LIMIT >> 2)                    # denominators grew close to 2**61 first


class TestDListInteger(TestDList):
    POSITIONS = "integer"


class TestUnnamedCellsInteger(TestUnnamedCells):
    POSITIONS = "integer"


class TestIntegerPositions(unittest.TestCase):
    def test_kind_and_labels(self):
        q = DList("Q", "integer")
        self.assertEqual(q.positions, "integer")
        with self.assertRaises(ValueError):
            DList("Q", "decimal")
        for i in range(20000):
            q.insert_before(f"v{i}", SINK)              # appends halve the gap to SINK: relabeling
        self.assertGreater(q.renumber_count, 0)
        self.assertEqual(q.index(SOURCE), float("-inf"))
        self.assertEqual(q.index(SINK), float("inf"))
        labels = [q.index(n) for n in q]
        self.assertTrue(all(isinstance(x, int) and 0 < x < 1 << 62 for x in labels))
        self.assertEqual(labels, sorted(labels))
        self.assertEqual(len(set(labels)), len(labels))


if __name__ == "__main__":
    unittest.main()
