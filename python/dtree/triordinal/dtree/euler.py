"""EulerTree: a directed tree encoded by one list, its Euler tour (part of Triordinal).

``from triordinal.dtree.euler import EulerTree``

An EulerTree keeps DTree's Q1 alone, with the closing cells that DTree 2.1.0 introduced: every
node with children has a closing cell directly after the last cell of its subtree, so the
subtree of u is the block from u to its closing cell (u alone for a leaf). Node u reaches node v
exactly when v's cell lies strictly inside u's block: two position comparisons, as in DTree.
This is the classical parenthesis (Euler-tour) encoding of a tree (Dietz 1982), maintained under
insertions on DTree's list; leaves need no closing cell.

The API is DTree's: names or handles, insert / insert_after / insert_before, delete,
delete_subtree, cut_n_paste, strict mode, and the constructed nodes VMin, VMax, UMin, UMax. In
one list a constructed node uses the end of each member's block in place of its Q2 position;
insertions keep the order of block ends, so constructed nodes stay valid as in DTree. ``Q2`` and
``q2`` do not exist.

For trees, the Euler tour holds the same information as DTree's two lists (Q2 is the post-order
reversed) and is faster to maintain; see docs/prior-art.md. Positions are rational by default;
``positions="integer"`` gives integer positions, faster to compare and renumbered more often.
"""

from __future__ import annotations

from triordinal.dtree.core import DNode, DTree, UMax, UMin, VMax, VMin, _lt2_euler, _reaches1

__all__ = ["EulerTree", "DNode", "VMin", "VMax", "UMin", "UMax"]


class EulerTree(DTree):
    """Single-rooted directed tree encoded by one list (Q1 with closing cells).

    ``EulerTree(tree_id="E1", strict=False, positions="rational")``; everything else as DTree.
    """

    _single = True
    _reach = staticmethod(_reaches1)
    _lt2 = staticmethod(_lt2_euler)

    def __init__(self, tree_id: str = "E1", strict: bool = False, positions: str = "rational") -> None:
        super().__init__(tree_id, strict, positions)
