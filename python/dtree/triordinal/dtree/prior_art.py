"""Prior art for the benchmarks: classical encodings of ancestry, implemented as fairly as the
DTree code itself, so that the benchmarks compare methods rather than implementations.

* EulerTour: the parenthesis (Euler-tour) encoding on one list. Every node has an open and a
  close cell in one DList; u is an ancestor of v exactly when v's open cell lies between u's open
  and close cells (Dietz 1982; maintained under insertions by order maintenance, Dietz & Sleator
  1987, Bender et al. 2002). Here the list is the same DList with rational positions that DTree
  uses, so the only difference to DTree is one list instead of two.
* PrePostNumbers: pre- and post-order numbers from a traversal, recomputed lazily: only before
  a query, and only if the tree has changed since the last traversal.
* IntList and EulerTourInt: the same Euler tour on a list with integer labels, as in classical
  order maintenance: a new cell gets the midpoint of its neighbors' labels in a universe of 2**62;
  when there is no integer left between them, the smallest surrounding region with enough room is
  relabeled evenly, with the same density rule as DList (Bender et al.). Compared with EulerTour,
  this isolates rational against integer positions.
* NumList and EulerTourNum: the same Euler tour on floating-point positions, binary (float, as
  C#'s double) or decimal (Decimal at 28 significant digits, as C#'s decimal). A new cell gets one
  unit beyond its neighbor next to SOURCE or SINK, as rational positions do; between two cells,
  a float gets the midpoint, and a decimal the left neighbor plus half the gap rounded at its most
  significant digit, as in the original List.cs of DTree 1.0.0 (Enis Olgac's prototype). When no
  representable position is left between the neighbors, a region is respaced evenly, with the
  same density rule. Compared with EulerTour, this isolates rational against floating-point
  positions.

Both answer and/or queries the best way their encoding allows: EulerTour with the same kind of
constructed points as DTree (minimum and maximum of the open and close positions over the set),
PrePostNumbers with the same points over its numbers. These classes serve the benchmarks and
their tests; they are not part of the DTree API.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from typing import Dict, Iterable, List, Optional

from triordinal.dlist import _GROWTH, _SLACK, DList, _Cell


def _lt(x: _Cell, y: _Cell) -> bool:
    return x.num * y.den < y.num * x.den


class ENode:
    """Handle of a node in an EulerTour: its open and close cells."""

    __slots__ = ("name", "o", "c", "owner")

    def __init__(self, name: str, owner: "EulerTour") -> None:
        self.name = name
        self.owner = owner
        self.o: Optional[_Cell] = None
        self.c: Optional[_Cell] = None


class EulerTour:
    """Parenthesis encoding on one list with rational positions.

    insert(parent, child) puts the open and close cells of child directly before the close cell
    of parent (child becomes the last child), O(1) plus the occasional local renumbering.
    It keeps no parent or child links (DTree does, for parent and child queries, sibling insertion,
    delete and cut_n_paste), so its insertions do less bookkeeping than DTree's.
    can_reach(u, v) is two position comparisons: open(u) < open(v) < close(u).
    """

    def __init__(self, name: str = "E") -> None:
        self._q = DList(name)
        self._nodes: Dict[str, ENode] = {}
        self.root: Optional[ENode] = None

    @property
    def list(self) -> DList:
        return self._q

    def get_node(self, name: str) -> ENode:
        return self._nodes[name]

    def _new(self, name: str, after: _Cell) -> ENode:
        n = ENode(name, self)
        n.o = self._q._insert_cell_after(name, after)
        n.c = self._q._insert_cell_after(None, n.o)
        n.o.node = n.c.node = n
        self._nodes[name] = n
        return n

    def insert(self, parent, child: str) -> ENode:
        if self.root is None:
            self.root = self._new(parent, self._q.first)
        p = parent if parent.__class__ is ENode else self._nodes[parent]
        if child in self._nodes:
            raise ValueError(f"child {child!r} is already in the tree")
        return self._new(child, p.c.prev)

    def can_reach(self, u, v) -> bool:
        """Same argument handling as DTree.can_reach: names or handles, foreign handles reach nothing."""
        if u.__class__ is ENode:
            if u.owner is not self:
                return False
        else:
            u = self._nodes.get(u)
            if u is None:
                return False
        if v.__class__ is ENode:
            if v.owner is not self:
                return False
        else:
            v = self._nodes.get(v)
            if v is None:
                return False
        a, b = u.o, v.o
        if not a.num * b.den < b.num * a.den:
            return False
        a, b = v.o, u.c
        return a.num * b.den < b.num * a.den

    def nodes(self) -> List[str]:
        return list(self._q)

    def euler_set(self, nodes: Iterable) -> "EulerSet":
        return EulerSet(self, nodes)


class EulerSet:
    """The constructed points of a node set in an Euler tour: the extreme open and close cells.

    reaches_all(u):     open(u) < min open(S) and max close(S) < close(u)        O(1)
    reached_by_all(v):  max open(S) < open(v) and close(v) < min close(S)        O(1)
    reaches_some(u):    the first member after u (by open position) lies in u's block   O(log k)
    reached_by_some(v): the last topmost member before v contains v                     O(log k)
    """

    def __init__(self, t: EulerTour, nodes: Iterable) -> None:
        ms = [n if n.__class__ is ENode else t.get_node(n) for n in nodes]
        ms = list({id(n): n for n in ms}.values())
        _sort_by_open(ms)
        self._m = ms
        self._keys = [_key(n.o) for n in ms]
        self._min_o = ms[0].o if ms else None
        self._max_o = ms[-1].o if ms else None
        self._min_c = self._max_c = None
        for n in ms:
            if self._min_c is None or _lt(n.c, self._min_c):
                self._min_c = n.c
            if self._max_c is None or _lt(self._max_c, n.c):
                self._max_c = n.c
        tops: List[ENode] = []
        for n in ms:                                   # by open position: ancestors come first
            if not (tops and _lt(n.o, tops[-1].c)):
                tops.append(n)
        self._tops = tops
        self._top_keys = [_key(n.o) for n in tops]

    def reaches_all(self, u: ENode) -> bool:
        if self._min_o is None:
            return True
        return _lt(u.o, self._min_o) and _lt(self._max_c, u.c)

    def reached_by_all(self, v: ENode) -> bool:
        if self._min_o is None:
            return True
        return _lt(self._max_o, v.o) and _lt(v.o, self._min_c)

    def reaches_some(self, u: ENode) -> bool:
        i = bisect_right(self._keys, _key(u.o))
        return i < len(self._m) and _lt(self._m[i].o, u.c)

    def reached_by_some(self, v: ENode) -> bool:
        i = bisect_left(self._top_keys, _key(v.o))
        return i > 0 and _lt(v.o, self._tops[i - 1].c)


class _Key:
    """Sort key of a cell position (exact rational comparison)."""

    __slots__ = ("num", "den")

    def __init__(self, cell: _Cell) -> None:
        self.num, self.den = cell.num, cell.den

    def __lt__(self, other: "_Key") -> bool:
        return self.num * other.den < other.num * self.den


def _key(cell: _Cell) -> _Key:
    return _Key(cell)


def _sort_by_open(ms: List[ENode]) -> None:
    ms.sort(key=lambda n: _Key(n.o))


class PrePostNumbers:
    """Pre- and post-order numbers, recomputed lazily: an insertion only marks them stale; the
    next query recomputes all of them with one traversal, O(n). Queries are O(1) otherwise."""

    def __init__(self) -> None:
        self.children: Dict[int, List[int]] = {}
        self.root: Optional[int] = None
        self.pre: Dict[int, int] = {}
        self.post: Dict[int, int] = {}
        self.stale = True
        self.recomputations = 0

    def insert(self, parent: int, child: int) -> None:
        if self.root is None:
            self.root = parent
        self.children.setdefault(parent, []).append(child)
        self.stale = True

    def refresh(self) -> None:
        pre, post, clock = {}, {}, 0
        children = self.children
        stack = [(self.root, False)]
        while stack:
            x, done = stack.pop()
            if done:
                post[x] = clock
                clock += 1
                continue
            pre[x] = clock
            clock += 1
            stack.append((x, True))
            ks = children.get(x)
            if ks:
                stack.extend((k, False) for k in reversed(ks))
        self.pre, self.post = pre, post
        self.stale = False
        self.recomputations += 1

    def can_reach(self, u: int, v: int) -> bool:
        if self.stale:
            self.refresh()
        pre, post = self.pre, self.post
        return pre[u] < pre[v] and post[v] < post[u]

    def number_set(self, nodes: Iterable[int]) -> "NumberSet":
        if self.stale:
            self.refresh()
        return NumberSet(self, nodes)


class NumberSet:
    """The constructed points of a node set over pre/post numbers (valid until the tree changes)."""

    def __init__(self, t: PrePostNumbers, nodes: Iterable[int]) -> None:
        pre, post = t.pre, t.post
        ms = sorted(set(nodes), key=pre.__getitem__)
        self._t = t
        self._keys = [pre[n] for n in ms]
        self._m = ms
        self._min_pre = self._keys[0] if ms else None
        self._max_pre = self._keys[-1] if ms else None
        self._min_post = min((post[n] for n in ms), default=None)
        self._max_post = max((post[n] for n in ms), default=None)
        tops: List[int] = []
        for n in ms:
            if not (tops and post[n] < post[tops[-1]]):
                tops.append(n)
        self._tops = tops
        self._top_keys = [pre[n] for n in tops]

    def reaches_all(self, u: int) -> bool:
        t = self._t
        return self._min_pre is None or (t.pre[u] < self._min_pre and self._max_post < t.post[u])

    def reached_by_all(self, v: int) -> bool:
        t = self._t
        return self._min_pre is None or (self._max_pre < t.pre[v] and t.post[v] < self._min_post)

    def reaches_some(self, u: int) -> bool:
        t = self._t
        i = bisect_right(self._keys, t.pre[u])
        return i < len(self._m) and t.post[self._m[i]] < t.post[u]

    def reached_by_some(self, v: int) -> bool:
        t = self._t
        i = bisect_left(self._top_keys, t.pre[v])
        return i > 0 and t.post[v] < t.post[self._tops[i - 1]]


class _ICell:
    __slots__ = ("name", "prev", "next", "label", "node")

    def __init__(self, name: Optional[str]) -> None:
        self.name = name
        self.prev: Optional[_ICell] = None
        self.next: Optional[_ICell] = None
        self.label = 0
        self.node = None


def _round_msd_int(half: int, base: int) -> int:
    """half (> 0) rounded half up at its most significant digit in the given base."""
    s = 1
    while s * base <= half:
        s *= base
    return ((half + s // 2) // s) * s


class IntList:
    """Doubly linked list with integer labels in [0, 2**62] (classical order maintenance).

    SOURCE has label 0, SINK 2**62. A new cell gets the midpoint of its neighbors; when they are
    adjacent integers, the smallest surrounding region with enough room is relabeled evenly. The
    region grows and must be sparser the larger it is, with the same constants as DList.
    """

    U = 1 << 62

    def __init__(self, name: str, msd: int = 0) -> None:
        """msd 0: the midpoint; msd 2 or 10: the left neighbor plus half the gap rounded at its most
        significant digit in that base (the rule of List.cs, applied to integers)."""
        self.name = name
        self.msd = msd
        self.first, self.last = _ICell("["), _ICell("]")
        self.first.next, self.last.prev = self.last, self.first
        self.first.label, self.last.label = 0, self.U
        self.renumber_count = 0
        self.renumber_moved = 0
        self.size = 0

    def _insert_cell_after(self, name: Optional[str], anchor: _ICell) -> _ICell:
        cell = _ICell(name)
        nxt = anchor.next
        cell.prev, cell.next = anchor, nxt
        anchor.next = nxt.prev = cell
        self.size += 1
        g = nxt.label - anchor.label
        if g >= 2:
            x = anchor.label + (_round_msd_int(g >> 1, self.msd) if self.msd else g >> 1)
            if not anchor.label < x < nxt.label:
                x = anchor.label + (g >> 1)
            cell.label = x
        else:
            self._rebalance(cell)
        return cell

    def _rebalance(self, cell: _ICell) -> None:
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
            room = right.label - left.label - 1
            if room >= m * need or (left is self.first and right is self.last):
                break
            k *= 2
            need *= _GROWTH
        if room < m:
            raise OverflowError("the label universe is full")
        c, base = lo, left.label
        for j in range(m):
            c.label = base + ((j + 1) * (room + 1)) // (m + 1)
            c = c.next
        self.renumber_count += 1
        self.renumber_moved += m

    def __iter__(self):
        c = self.first.next
        while c is not self.last:
            if c.name is not None:
                yield c.name
            c = c.next


class EulerTourInt:
    """The Euler tour of EulerTour on an IntList: integer positions instead of rational ones."""

    def __init__(self, name: str = "E", msd: int = 0) -> None:
        self._q = IntList(name, msd)
        self._nodes: Dict[str, "ENodeInt"] = {}
        self.root: Optional["ENodeInt"] = None

    @property
    def list(self) -> IntList:
        return self._q

    def get_node(self, name: str) -> "ENodeInt":
        return self._nodes[name]

    def _new(self, name: str, after: _ICell) -> "ENodeInt":
        n = ENodeInt(name, self)
        n.o = self._q._insert_cell_after(name, after)
        n.c = self._q._insert_cell_after(None, n.o)
        n.o.node = n.c.node = n
        self._nodes[name] = n
        return n

    def insert(self, parent, child: str) -> "ENodeInt":
        if self.root is None:
            self.root = self._new(parent, self._q.first)
        p = parent if parent.__class__ is ENodeInt else self._nodes[parent]
        if child in self._nodes:
            raise ValueError(f"child {child!r} is already in the tree")
        return self._new(child, p.c.prev)

    def can_reach(self, u, v) -> bool:
        """Same argument handling as DTree.can_reach and EulerTour.can_reach."""
        if u.__class__ is ENodeInt:
            if u.owner is not self:
                return False
        else:
            u = self._nodes.get(u)
            if u is None:
                return False
        if v.__class__ is ENodeInt:
            if v.owner is not self:
                return False
        else:
            v = self._nodes.get(v)
            if v is None:
                return False
        x = v.o.label
        return u.o.label < x < u.c.label

    def nodes(self) -> List[str]:
        return list(self._q)


class ENodeInt:
    __slots__ = ("name", "o", "c", "owner")

    def __init__(self, name: str, owner: EulerTourInt) -> None:
        self.name = name
        self.owner = owner
        self.o: Optional[_ICell] = None
        self.c: Optional[_ICell] = None


class _NCell:
    __slots__ = ("name", "prev", "next", "label", "node")

    def __init__(self, name: Optional[str]) -> None:
        self.name = name
        self.prev = self.next = None
        self.label = None
        self.node = None


def _round_msd_float(half: float, base: int) -> float:
    """half (> 0) rounded at its most significant digit in the given base, found by its logarithm."""
    s = float(base) ** math.floor(math.log(half, base))
    if s * base <= half:
        s *= base
    elif s > half:
        s /= base
    return round(half / s) * s if s > 0 else half


class NumList:
    """Doubly linked list with floating-point positions: kind "float" (binary, 53-bit mantissa) or
    "decimal" (28 significant digits). SOURCE and SINK act as -infinity and +infinity."""

    def __init__(self, name: str, kind: str = "float", msd: Optional[int] = None) -> None:
        """msd: 0 for the midpoint, 2 or 10 for the rule of List.cs in that base; default: the
        midpoint for float, base 10 for decimal (as List.cs)."""
        if kind == "float":
            self._n = float
        elif kind == "decimal":
            from decimal import Decimal, getcontext
            if getcontext().prec != 28:
                raise ValueError("NumList('decimal') expects the default decimal precision of 28 digits")
            self._n = Decimal
        else:
            raise ValueError(kind)
        self.name, self.kind = name, kind
        self.msd = (10 if kind == "decimal" else 0) if msd is None else msd
        if kind == "decimal" and self.msd not in (0, 10):
            raise ValueError("decimal positions: msd 0 or 10")
        self.first, self.last = _NCell("["), _NCell("]")
        self.first.next, self.last.prev = self.last, self.first
        self.renumber_count = 0
        self.renumber_moved = 0
        self._two = self._n(2)
        self._q28 = self._n(1).scaleb(-28) if kind == "decimal" else None

    def _insert_cell_after(self, name: Optional[str], anchor: _NCell) -> _NCell:
        cell = _NCell(name)
        a, b = anchor, anchor.next
        cell.prev, cell.next = a, b
        a.next = b.prev = cell
        if a is self.first:
            cell.label = self._n(0) if b is self.last else b.label - 1
        elif b is self.last:
            cell.label = a.label + 1
        else:
            x = self._between(a.label, b.label)
            if x is None:
                self._rebalance(cell)
            else:
                cell.label = x
        return cell

    def _fit(self, x):
        """A decimal as C#'s decimal can hold it: at most 28 decimal places (28 significant digits
        come from the context). Python's Decimal would otherwise go down to 10**-999999."""
        if self.kind == "decimal" and x.as_tuple().exponent < -28:
            x = x.quantize(self._q28)
        return x

    def _between(self, lo, hi):
        """A position strictly between lo and hi, or None if there is none."""
        if self.msd:
            # half the gap, rounded at its most significant digit (List.cs: Middle)
            half = (hi - lo) / self._two
            if half > 0:
                if self.kind == "decimal":
                    x = self._fit(lo + half.quantize(self._n(1).scaleb(half.adjusted()), rounding="ROUND_HALF_UP"))
                else:
                    x = lo + _round_msd_float(half, self.msd)
                if lo < x < hi:
                    return x
        mid = self._fit((lo + hi) / self._two)
        return mid if lo < mid < hi else None

    def _rebalance(self, cell: _NCell) -> None:
        n = self._n
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
                labels = [n(j - m // 2) for j in range(m)]
                break
            if left is self.first:
                labels = [right.label - (m - j) for j in range(m)]
                break
            if right is self.last:
                labels = [left.label + (j + 1) for j in range(m)]
                break
            step = (right.label - left.label) / n(m + 1)
            if self.kind == "decimal" and self.msd and step > 0:
                # short positions after respacing too: the step cut at its most significant digit
                step = self._fit(step.quantize(n(1).scaleb(step.adjusted()), rounding="ROUND_DOWN"))
            tiny = self._fit(step / n(need))
            if left.label + tiny > left.label and right.label - tiny < right.label:
                labels = [self._fit(left.label + step * (j + 1)) for j in range(m)]
                if all(x < y for x, y in zip([left.label] + labels, labels + [right.label])):
                    break
            k *= 2
            need *= _GROWTH
        c = lo
        for x in labels:
            c.label = x
            c = c.next
        self.renumber_count += 1
        self.renumber_moved += m

    def __iter__(self):
        c = self.first.next
        while c is not self.last:
            if c.name is not None:
                yield c.name
            c = c.next


class ENodeNum:
    __slots__ = ("name", "o", "c", "owner")

    def __init__(self, name: str, owner: "EulerTourNum") -> None:
        self.name = name
        self.owner = owner
        self.o = self.c = None


class EulerTourNum:
    """The Euler tour of EulerTour on a NumList: floating-point positions (kind "float" or "decimal")."""

    def __init__(self, name: str = "E", kind: str = "float", msd: Optional[int] = None) -> None:
        self._q = NumList(name, kind, msd)
        self._nodes: Dict[str, ENodeNum] = {}
        self.root: Optional[ENodeNum] = None

    @property
    def list(self) -> NumList:
        return self._q

    def get_node(self, name: str) -> ENodeNum:
        return self._nodes[name]

    def _new(self, name: str, after: _NCell) -> ENodeNum:
        n = ENodeNum(name, self)
        n.o = self._q._insert_cell_after(name, after)
        n.c = self._q._insert_cell_after(None, n.o)
        n.o.node = n.c.node = n
        self._nodes[name] = n
        return n

    def insert(self, parent, child: str) -> ENodeNum:
        if self.root is None:
            self.root = self._new(parent, self._q.first)
        p = parent if parent.__class__ is ENodeNum else self._nodes[parent]
        if child in self._nodes:
            raise ValueError(f"child {child!r} is already in the tree")
        return self._new(child, p.c.prev)

    def can_reach(self, u, v) -> bool:
        """Same argument handling as DTree.can_reach and EulerTour.can_reach."""
        if u.__class__ is ENodeNum:
            if u.owner is not self:
                return False
        else:
            u = self._nodes.get(u)
            if u is None:
                return False
        if v.__class__ is ENodeNum:
            if v.owner is not self:
                return False
        else:
            v = self._nodes.get(v)
            if v is None:
                return False
        x = v.o.label
        return u.o.label < x < u.c.label

    def nodes(self) -> List[str]:
        return list(self._q)
