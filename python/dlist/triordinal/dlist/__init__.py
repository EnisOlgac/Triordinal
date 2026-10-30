"""DList: a doubly linked list with rational positions and an O(1) precedence test.

Shared by triordinal-dtree and triordinal-dgraph. Positions are fractions: a new
element gets the mediant (a+c)/(b+d) of its neighbors a/b and c/d, which always lies
strictly between them, so normally no other element moves. Rational positions were
Enis Olgac's idea. Only when a denominator would exceed 64 bits is the smallest
surrounding region with enough room renumbered with simple fractions k/2**32; larger
regions must be sparser before they are accepted (as in Bender et al., ESA 2002).

Integer positions are offered as well, ``DList(name, positions="integer")``: a new element
gets the midpoint of its neighbors' labels in [0, 2**62], as in classical order maintenance,
and when no integer is left between them the smallest surrounding region with enough room is
relabeled evenly, with the same density rule. In the Triordinal benchmarks, integer positions
are faster to compare and rational positions are renumbered far less often.

A list may also hold unnamed cells: they have a position like any other cell but no
name, so iteration, ``next``/``prev`` and all lookups by name pass over them. DTree uses
them as the closing cell of each node with children, which marks the end of its subtree.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, Iterable, Iterator, List, Optional

SOURCE = "["
SINK = "]"

_Q = 1 << 32  # denominator used when a crowded region is renumbered
_LIMIT = 64  # renumber when a denominator would exceed this many bits
_SLACK = 16  # after renumbering, neighbors are at least this many 1/_Q apart
_GROWTH = 2  # each doubling of the region raises the required spacing by this factor
_U = 1 << 62  # integer positions: SOURCE has label 0, SINK label _U

POSITIONS = ("rational", "integer")


class _Cell:
    __slots__ = ("name", "prev", "next", "num", "den", "node")

    def __init__(self, name: Optional[str]) -> None:
        self.name = name  # None for an unnamed cell
        self.prev: Optional[_Cell] = None
        self.next: Optional[_Cell] = None
        self.num = 0
        self.den = 1
        self.node = None  # the node owning this cell (a DTree or DGraph node handle)


class DList:
    """Doubly linked list with rational positions (O(1) precedence test).

    Positions are fractions num/den. A new node gets the mediant
    (a+c)/(b+d) of its neighbors a/b and c/d, which always lies strictly
    between them; SOURCE and SINK act as -1/0 and +1/0. Nothing else moves.
    Only when a denominator would exceed _LIMIT bits is a small surrounding
    region renumbered with simple fractions k/_Q.
    """

    def __init__(self, name: str, positions: str = "rational") -> None:
        if positions not in POSITIONS:
            raise ValueError(f"positions must be one of {POSITIONS}, not {positions!r}")
        self.name = name
        self.positions = positions
        self._integer = positions == "integer"
        self._cells: Dict[str, _Cell] = {}
        self.first = self._new(SOURCE)
        self.last = self._new(SINK)
        self.first.next = self.last
        self.last.prev = self.first
        if self._integer:
            self.first.num, self.last.num = 0, _U  # integer labels (den 1) in [0, 2**62]
        else:
            self.first.num, self.first.den = -1, 0  # -infinity
            self.last.num, self.last.den = 1, 0  # +infinity
        # Statistics: how often positions were renumbered and how many moved.
        self.renumber_count = 0
        self.renumber_moved = 0

    # -- internals --------------------------------------------------------
    def _new(self, name: str) -> _Cell:
        cell = _Cell(name)
        self._cells[name] = cell
        return cell

    @staticmethod
    def _lt(x: _Cell, y: _Cell) -> bool:
        """x lies strictly left of y, by comparing x.num/x.den with y.num/y.den."""
        if x.den and y.den:
            return x.num * y.den < y.num * x.den
        if x.den == 0 and y.den == 0:
            return x.num < y.num
        return (x.num if x.den == 0 else 0) < (y.num if y.den == 0 else 0)

    def _link_after(self, cell: _Cell, prev: _Cell) -> None:
        nxt = prev.next
        cell.prev, cell.next = prev, nxt
        prev.next = cell
        nxt.prev = cell
        if self._integer:
            g = nxt.num - prev.num
            if g >= 2:
                cell.num, cell.den = prev.num + (g >> 1), 1  # the midpoint
            else:
                self._rebalance_integer(cell)
            return
        if prev is self.first and nxt is self.last:
            cell.num, cell.den = 0, 1  # first node of an empty list
            return
        # Mediant of the neighbors. Next to SOURCE (-1/0) or SINK (+1/0) this
        # steps by one whole unit, so a list can grow at either end forever
        # without renumbering (positives to the right, negatives to the left).
        cell.num = prev.num + nxt.num
        cell.den = prev.den + nxt.den
        if cell.den.bit_length() > _LIMIT:
            self._rebalance(cell)

    def _rebalance(self, cell: _Cell) -> None:
        """Renumber the smallest region around ``cell`` that has room, using fractions k/_Q."""
        q = _Q
        lo = hi = cell
        m, k, need = 1, 1, _SLACK
        while True:
            for _ in range(k):
                if lo.prev is not self.first:
                    lo = lo.prev
                    m += 1
                if hi.next is not self.last:
                    hi = hi.next
                    m += 1
            left, right = lo.prev, hi.next
            if left is self.first and right is self.last:
                ks = [(j - m // 2) * q for j in range(m)]
                break
            if left is self.first:
                top = -((-right.num * q) // right.den)  # ceil(right * q)
                ks = [top - (m - j) * q for j in range(m)]
                break
            if right is self.last:
                bottom = (left.num * q) // left.den  # floor(left * q)
                ks = [bottom + (j + 1) * q for j in range(m)]
                break
            bottom = (left.num * q) // left.den
            top = -((-right.num * q) // right.den)
            room = top - bottom - 1  # integers k with left < k/q < right
            if room >= m * need:
                ks = [bottom + ((j + 1) * (room + 1)) // (m + 1) for j in range(m)]
                break
            # Larger regions must be sparser before they are accepted (as in
            # Bender et al.), so a renumbered region keeps spare room and the
            # next overflow nearby can again be handled locally.
            k *= 2
            need *= _GROWTH
        c = lo
        for kv in ks:
            c.num, c.den = kv, q
            c = c.next
        self.renumber_count += 1
        self.renumber_moved += m

    def _rebalance_integer(self, cell: _Cell) -> None:
        """Relabel the smallest region around ``cell`` that has room, evenly (integer positions)."""
        lo = hi = cell
        m, k, need = 1, 1, _SLACK
        while True:
            for _ in range(k):
                if lo.prev is not self.first:
                    lo = lo.prev
                    m += 1
                if hi.next is not self.last:
                    hi = hi.next
                    m += 1
            left, right = lo.prev, hi.next
            room = right.num - left.num - 1  # integers strictly between the two
            if room >= m * need or (left is self.first and right is self.last):
                break
            k *= 2
            need *= _GROWTH
        if room < m:
            raise OverflowError(f"{self.name}: no integer positions left")
        c, base = lo, left.num
        for j in range(m):
            c.num, c.den = base + ((j + 1) * (room + 1)) // (m + 1), 1
            c = c.next
        self.renumber_count += 1
        self.renumber_moved += m

    def _unlink(self, cell: _Cell) -> None:
        cell.prev.next = cell.next
        cell.next.prev = cell.prev
        cell.prev = cell.next = None

    # -- cell-level operations for the node handles of DTree and DGraph ---------------
    def _insert_cell_after(self, name: Optional[str], anchor: _Cell) -> _Cell:
        """A new cell directly after ``anchor``; ``name`` None makes an unnamed cell.
        The position is computed while linking; a name is registered only afterwards."""
        if name is not None and name in self._cells:
            raise ValueError(f"{name!r} is already in {self.name}")
        if anchor is self.last:
            raise ValueError("nothing can follow SINK")
        cell = _Cell(name)
        self._link_after(cell, anchor)
        if name is not None:
            self._cells[name] = cell
        return cell

    def _remove_cell(self, cell: _Cell) -> None:
        self._unlink(cell)
        if cell.name is not None:
            del self._cells[cell.name]

    def _cut_cells(self, a: _Cell, b: _Cell, forget: bool) -> List[_Cell]:
        """Unlink the contiguous block a..b and return its cells in order. With ``forget``
        their names are removed from the list; otherwise they stay registered, to be pasted
        again with _paste_cells_after (a move)."""
        cells, c = [], a
        while True:
            cells.append(c)
            if c is b:
                break
            c = c.next
        a.prev.next = b.next
        b.next.prev = a.prev
        a.prev = b.next = None
        if forget:
            for c in cells:
                if c.name is not None:
                    del self._cells[c.name]
        return cells

    def _paste_cells_after(self, cells: List[_Cell], anchor: _Cell) -> None:
        """Link cut cells, in order, directly after ``anchor``; they get new positions."""
        for c in cells:
            self._link_after(c, anchor)
            anchor = c

    # -- public -----------------------------------------------------------
    def __contains__(self, name: str) -> bool:
        return name in self._cells

    # Names follow List.cs: Source/Sink, First/Last, Prev/Next, Index,
    # IsAllocated, IsLeftOf ... IsSelfOrRightOf, InsAfter/InsBefore, IsSameAs.

    @property
    def source(self) -> str:
        return self.first.name

    @property
    def sink(self) -> str:
        return self.last.name

    def index(self, name: str):
        """Position of ``name`` as a Fraction (SOURCE/SINK: -inf/+inf), or None if absent (List.cs: Index)."""
        cell = self._cells.get(name)
        if cell is None:
            return None
        if cell is self.first:
            return float("-inf")
        if cell is self.last:
            return float("inf")
        return cell.num if self._integer else Fraction(cell.num, cell.den)

    label = index

    def is_allocated(self, name: str) -> bool:
        return name in self._cells

    def is_not_allocated(self, name: str) -> bool:
        return name not in self._cells

    def next(self, name: str) -> Optional[str]:
        """Name of the next named cell (SINK after the last one), None after SINK."""
        nxt = self._cells[name].next
        while nxt is not None and nxt.name is None:
            nxt = nxt.next
        return nxt.name if nxt else None

    def prev(self, name: str) -> Optional[str]:
        """Name of the previous named cell (SOURCE before the first one), None before SOURCE."""
        prv = self._cells[name].prev
        while prv is not None and prv.name is None:
            prv = prv.prev
        return prv.name if prv else None

    def is_left_of(self, v: str, u: str) -> bool:
        return self._lt(self._cells[v], self._cells[u])

    def is_self_or_left_of(self, v: str, u: str) -> bool:
        return v == u or self._lt(self._cells[v], self._cells[u])

    def is_right_of(self, v: str, u: str) -> bool:
        return self._lt(self._cells[u], self._cells[v])

    def is_self_or_right_of(self, v: str, u: str) -> bool:
        return v == u or self._lt(self._cells[u], self._cells[v])

    def precedes(self, u: str, v: str) -> bool:
        """Strict order: u lies left of v (same as is_left_of)."""
        x, y = self._cells[u], self._cells[v]
        if x.den and y.den:
            return x.num * y.den < y.num * x.den
        return self._lt(x, y)

    def _cell_for(self, name: str) -> _Cell:
        """Existing cell (unlinked first, so it is moved) or a new one."""
        cell = self._cells.get(name)
        if cell is None:
            return self._new(name)
        self._unlink(cell)
        return cell

    def insert_after(self, name: str, anchor: str) -> None:
        """Place ``name`` directly after ``anchor``; moves it if already present (List.cs: InsAfter)."""
        if name in (SOURCE, SINK):
            raise ValueError(f"the markers {SOURCE} and {SINK} cannot be inserted or moved")
        if name == anchor:
            return
        if anchor == SINK:
            return self.insert_before(name, SINK)
        a = self._cells[anchor]
        if a.next is not None and a.next.name == name:
            return
        cell = self._cell_for(name)
        self._link_after(cell, self._cells[anchor])

    def insert_before(self, name: str, anchor: str) -> None:
        """Place ``name`` directly before ``anchor``; moves it if already present (List.cs: InsBefore)."""
        if name in (SOURCE, SINK):
            raise ValueError(f"the markers {SOURCE} and {SINK} cannot be inserted or moved")
        if name == anchor:
            return
        if anchor == SOURCE:
            return self.insert_after(name, SOURCE)
        a = self._cells[anchor]
        if a.prev is not None and a.prev.name == name:
            return
        cell = self._cell_for(name)
        self._link_after(cell, self._cells[anchor].prev)

    def is_same_as(self, other: "DList") -> bool:
        """True if both lists hold the same nodes in the same order (List.cs: IsSameAs)."""
        return list(self) == list(other)

    def remove(self, name: str) -> None:
        if name in (SOURCE, SINK):
            raise ValueError("markers cannot be removed")
        self._unlink(self._cells.pop(name))

    def cut_block(self, first: str, last: str) -> List[str]:
        """Remove the contiguous block first..last and return its names in order
        (unnamed cells inside the block are removed as well)."""
        if first in (SOURCE, SINK) or last in (SOURCE, SINK):
            raise ValueError("markers cannot be removed")
        cells = self._cut_cells(self._cells[first], self._cells[last], forget=True)
        return [c.name for c in cells if c.name is not None]

    def paste_block_after(self, names: List[str], anchor: str) -> None:
        for n in names:
            self.insert_after(n, anchor)
            anchor = n

    def __iter__(self) -> Iterator[str]:
        cell = self.first.next
        while cell is not self.last:
            if cell.name is not None:
                yield cell.name
            cell = cell.next

    def __len__(self) -> int:
        """Number of named cells, without the markers."""
        return len(self._cells) - 2

    def to_list(self, with_markers: bool = False) -> List[str]:
        body = list(self)
        return [SOURCE, *body, SINK] if with_markers else body

    def __repr__(self) -> str:
        return f"{self.name}: [{', '.join(self)}]"

__all__ = ["DList", "SOURCE", "SINK", "POSITIONS"]
__version__ = "2.2.0"
