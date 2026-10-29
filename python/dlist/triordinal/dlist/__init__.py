"""DList: a doubly linked list with rational positions and an O(1) precedence test.

Shared by triordinal-dtree and triordinal-dgraph. Positions are fractions: a new
element gets the mediant (a+c)/(b+d) of its neighbors a/b and c/d, which always lies
strictly between them, so normally no other element moves. Rational positions were
Enis Olgac's idea. Only when a denominator would exceed 64 bits is the smallest
surrounding region with enough room renumbered with simple fractions k/2**32; larger
regions must be sparser before they are accepted (as in Bender et al., ESA 2002).
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


class _Cell:
    __slots__ = ("name", "prev", "next", "num", "den", "node")

    def __init__(self, name: str) -> None:
        self.name = name
        self.prev: Optional[_Cell] = None
        self.next: Optional[_Cell] = None
        self.num = 0
        self.den = 1
        self.node: Optional["DNode"] = None  # the tree node owning this cell (DTree only)


class DList:
    """Doubly linked list with rational positions (O(1) precedence test).

    Positions are fractions num/den. A new node gets the mediant
    (a+c)/(b+d) of its neighbors a/b and c/d, which always lies strictly
    between them; SOURCE and SINK act as -1/0 and +1/0. Nothing else moves.
    Only when a denominator would exceed _LIMIT bits is a small surrounding
    region renumbered with simple fractions k/_Q.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._cells: Dict[str, _Cell] = {}
        self.first = self._new(SOURCE)
        self.last = self._new(SINK)
        self.first.next = self.last
        self.last.prev = self.first
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

    def _unlink(self, cell: _Cell) -> None:
        cell.prev.next = cell.next
        cell.next.prev = cell.prev
        cell.prev = cell.next = None

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
        if cell.den == 0:
            return float("inf") if cell.num > 0 else float("-inf")
        return Fraction(cell.num, cell.den)

    label = index

    def is_allocated(self, name: str) -> bool:
        return name in self._cells

    def is_not_allocated(self, name: str) -> bool:
        return name not in self._cells

    def next(self, name: str) -> Optional[str]:
        nxt = self._cells[name].next
        return nxt.name if nxt else None

    def prev(self, name: str) -> Optional[str]:
        prv = self._cells[name].prev
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
        """Remove the contiguous block first..last and return its names in order."""
        a, b = self._cells[first], self._cells[last]
        names, cell = [], a
        while True:
            names.append(cell.name)
            if cell is b:
                break
            cell = cell.next
        a.prev.next = b.next
        b.next.prev = a.prev
        for n in names:
            self._cells.pop(n)
        return names

    def paste_block_after(self, names: List[str], anchor: str) -> None:
        for n in names:
            self.insert_after(n, anchor)
            anchor = n

    def __iter__(self) -> Iterator[str]:
        cell = self.first.next
        while cell is not self.last:
            yield cell.name
            cell = cell.next

    def to_list(self, with_markers: bool = False) -> List[str]:
        body = list(self)
        return [SOURCE, *body, SINK] if with_markers else body

    def __repr__(self) -> str:
        return f"{self.name}: [{', '.join(self)}]"

__all__ = ["DList", "SOURCE", "SINK"]
__version__ = "2.0.0"
