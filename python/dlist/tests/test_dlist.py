"""Tests for DList on its own: order, precedence and renumbering against a plain Python list."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triordinal.dlist import SINK, SOURCE, DList  # noqa: E402


class TestDList(unittest.TestCase):
    def check(self, q, ref):
        self.assertEqual(list(q), ref)
        for _ in range(200):
            a, b = random.sample(ref, 2) if len(ref) > 1 else (ref[0], ref[0])
            self.assertEqual(q.precedes(a, b), ref.index(a) < ref.index(b))

    def test_random_inserts_and_removes(self):
        rnd = random.Random(1)
        q, ref = DList("Q"), []
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
        q, ref = DList("Q"), ["a", "b"]
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
        q = DList("Q")
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
        q = DList("Q")
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


if __name__ == "__main__":
    unittest.main()
