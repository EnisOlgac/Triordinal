"""The whole DTree test suite once more for each variant: DTree with integer positions, and
EulerTree (one list) with rational and with integer positions."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "dlist"))

import test_dtree as base  # noqa: E402
from triordinal.dtree import DTree  # noqa: E402
from triordinal.dtree.euler import EulerTree  # noqa: E402


class DTreeInteger(DTree):
    def __init__(self, tree_id="P1", strict=False, positions="integer"):
        super().__init__(tree_id, strict, positions)


class EulerRational(EulerTree):
    def __init__(self, tree_id="P1", strict=False, positions="rational"):
        super().__init__(tree_id, strict, positions)


class EulerInteger(EulerTree):
    def __init__(self, tree_id="P1", strict=False, positions="integer"):
        super().__init__(tree_id, strict, positions)


SUITES = [base.TestDocumentedExamples, base.TestVNodes, base.TestNodeHandles, base.TestSubtreeEnd,
          base.TestAgainstReference, base.TestSiblingInsert, base.TestNoSizeLimit, base.TestReviewPatterns,
          base.TestNoPartialState, base.TestReadOnlyProjections, base.TestStrict, base.TestMembersAreNodes,
          base.TestIsRoot]


def _variant(cls, tree_cls):
    class Variant(cls):
        def setUp(self):
            self._saved = base.DTree
            base.DTree = tree_cls
            super().setUp()

        def tearDown(self):
            base.DTree = self._saved
            super().tearDown()

    Variant.__name__ = f"{cls.__name__}_{tree_cls.__name__}"
    Variant.__qualname__ = Variant.__name__
    return Variant


for _tree in (DTreeInteger, EulerRational, EulerInteger):
    for _suite in SUITES:
        _v = _variant(_suite, _tree)
        globals()[_v.__name__] = _v
del _tree, _suite, _v


class TestEulerSpecifics(unittest.TestCase):
    def test_no_q2(self):
        t = EulerTree()
        t.insert("A", "B")
        with self.assertRaises(AttributeError):
            t.Q2
        with self.assertRaises(AttributeError):
            t.q2
        self.assertEqual(repr(t), "EulerTree('E1', size=2)\n  E1.Q1: [A, B]")
        self.assertEqual((t.positions, EulerTree(positions="integer").positions), ("rational", "integer"))
        with self.assertRaises(ValueError):
            EulerTree(positions="decimal")

    def test_leaves_need_no_closing_cell(self):
        t = EulerTree()
        for c in "BCD":
            t.insert("A", c)
        self.assertEqual(base.raw_cells(t._q1), ["A", "B", "C", "D", ")A"])

    def test_same_answers_as_dtree(self):
        for seed in range(5):
            d, ref, rnd = base.random_tree(150, seed)
            e = EulerTree(positions="integer")
            for v in d.q1[1:]:
                e.insert(d.get_parent(v), v)
            self.assertEqual(e.q1, d.q1)
            nodes = d.q1
            for _ in range(500):
                u, v = rnd.choice(nodes), rnd.choice(nodes)
                self.assertEqual(e.can_reach(u, v), d.can_reach(u, v))


if __name__ == "__main__":
    unittest.main()
