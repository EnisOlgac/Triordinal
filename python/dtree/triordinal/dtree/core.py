"""DTree 3.0: a single-rooted directed tree on one projection, with its structure in the vertices.

Design by Enis Olgac (Nov 2026); this implementation was written with Claude (Anthropic) and is
checked against a brute-force model in ``tests/``. DTree up to 2.4.2 kept two projections, Q1 and
Q2; it remains available for comparison as ``triordinal.dtree.two_lists.DTree``.

Structure
---------
A vertex keeps

* its parent,
* its kids list, a property of the vertex: read from one end it is left to right (LR), from the
  other right to left (RL),
* its handle in its parent's kids list (the cell that represents it there), and
* its cell in the projection Q1: one DList, the pre-order with kids LR. Positions are rational
  (the default) or integer.

The block of a vertex in Q1 runs from its own cell to just before its *delimiter*: its right
sibling, or, when it is the last kid, the delimiter of its parent (SINK above the root). In Prolog
terms the block is a difference list whose tail is the delimiter. No closing cells are stored.

Reachability
------------
    u reaches v  <=>  cell(u) < cell(v) < cell(delimiter(u))

``can_reach`` decides this as a cascade of local steps:

1. v is not right of u in Q1: no.
2. u has no kids: no.
3. u has a right sibling (or is the root): compare v with it.
4. u's last kid: v up to it is reached; if it is a leaf, its next cell in Q1 is u's delimiter.
5. Otherwise find the delimiter: up through the ancestors that are last kids.

Step 5 crosses a sequence of only kids (a *vertical run*, a list standing upright inside the tree)
in one step: the members of a run share one run object that knows the run's top. When a vertex of a
run gets a second kid, the run is cut there; when a vertex is left with one kid, its kid's run joins
its own. Cuts and joins renew the run object of the shorter part only, so a cut near either end of a
long run is cheap. A tree that is nothing but a sequence is a list; use ``DList`` for it.

Insertion
---------
A new kid goes into Q1 directly after its parent when it is the first kid, directly before its
right sibling when it has one, and before its parent's delimiter when it is appended as the last
kid; only the last case looks for the delimiter.
"""

from __future__ import annotations

import os
from functools import cmp_to_key
from typing import Dict, Iterable, Iterator, List, Optional

from triordinal.dlist import SINK, SOURCE, DList

_lt = DList._lt


class _Kid:
    """A cell of a kids list; it represents one kid."""

    __slots__ = ("prev", "next", "node")

    def __init__(self, node: "DNode") -> None:
        self.prev: Optional[_Kid] = None
        self.next: Optional[_Kid] = None
        self.node = node


class _Run:
    """A vertical run, shared by its members: its top and its number of members."""

    __slots__ = ("top", "size")

    def __init__(self, top: "DNode", size: int = 1) -> None:
        self.top, self.size = top, size


class DNode:
    """Handle of a vertex. Valid while the vertex is in its tree."""

    __slots__ = ("name", "up", "kh", "kt", "h", "c", "run", "owner")

    def __init__(self, name: str, owner: "DTree") -> None:
        self.name = name
        self.owner: Optional[DTree] = owner
        self.up: Optional[DNode] = None
        self.kh: Optional[_Kid] = None       # kids list, read LR from here
        self.kt: Optional[_Kid] = None       # kids list, read RL from here
        self.h: Optional[_Kid] = None        # this vertex's cell in its parent's kids list
        self.c = None                        # this vertex's cell in Q1
        self.run: Optional[_Run] = None      # its vertical run; None: a run of its own

    @property
    def parent(self) -> Optional["DNode"]:
        return self.up

    @property
    def children(self) -> List["DNode"]:
        out, k = [], self.kh
        while k is not None:
            out.append(k.node)
            k = k.next
        return out

    @property
    def is_in_tree(self) -> bool:
        return self.owner is not None

    def __repr__(self) -> str:
        return f"DNode({self.name!r})"


class DTree:
    """Single-rooted directed tree on one projection (see the module docstring)."""

    def __init__(self, tree_id: str = "P1", positions: str = "rational") -> None:
        self.tree_id = tree_id
        self._q = DList(f"{tree_id}.Q1", positions)
        self._nodes: Dict[str, DNode] = {}
        self._root: Optional[DNode] = None
        self.climb_steps = 0       # steps taken looking for delimiters
        self.run_steps = 0         # vertices given a new run object by cuts and joins

    @property
    def positions(self) -> str:
        return self._q.positions

    # -- construction from a description -----------------------------------------------
    @classmethod
    def from_file(cls, path: str, tree_id: Optional[str] = None, positions: str = "rational") -> "DTree":
        """Read the .csx description format.

        ``parent: child1; child2`` appends the children as last kids of ``parent``;
        ``sibling > child1; child2`` inserts them directly after ``sibling`` (in that order),
        ``sibling < child1; child2`` directly before it. Empty lines and lines starting with
        ``#``, ``--`` or ``**`` are skipped, ``@@`` ends the description; any other line without
        ``:``, ``>`` or ``<`` raises ValueError.
        """
        tree = cls(tree_id or os.path.splitext(os.path.basename(path))[0], positions)
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith(("#", "--", "**")):
                    continue
                if line.startswith("@@"):
                    break
                tree.add_line(line)
        return tree

    def add_line(self, line: str) -> List[DNode]:
        """Apply one line of the description format; returns the new handles."""
        at = min((i for i in (line.find(":"), line.find(">"), line.find("<")) if i >= 0), default=-1)
        if at < 0:
            raise ValueError(f"no ':', '>' or '<' in {line!r}")
        op, anchor = line[at], line[:at].strip()
        added = []
        for child in (c.strip() for c in line[at + 1:].split(";")):
            if not child:
                continue
            if op == ":":
                added.append(self.insert(anchor, child))
            elif op == ">":
                added.append(self.insert_after(anchor, child))
                anchor = child                       # the next one goes after this one
            else:
                added.append(self.insert_before(anchor, child))
        return added

    # -- names and handles ------------------------------------------------------------------
    @staticmethod
    def _check_name(name) -> None:
        if not isinstance(name, str):
            raise TypeError(f"a node name must be a string, not {type(name).__name__}")
        if not name or name in (SOURCE, SINK):
            raise ValueError(f"invalid node name {name!r}")

    def _node(self, x) -> DNode:
        if isinstance(x, DNode):
            if x.owner is not self:
                raise KeyError(f"{x.name!r} is not in this tree")
            return x
        return self._nodes[x]

    def get_node(self, name: str) -> DNode:
        """Handle of the vertex called ``name``. Raises KeyError if absent."""
        return self._nodes[name]

    def try_get_node(self, name: str) -> Optional[DNode]:
        return self._nodes.get(name)

    def __contains__(self, node) -> bool:
        if isinstance(node, DNode):
            return node.owner is self
        return node in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def root(self) -> Optional[str]:
        return None if self._root is None else self._root.name

    @property
    def renumber_count(self) -> int:
        """How often a region of Q1 was renumbered."""
        return self._q.renumber_count

    # -- kids lists ---------------------------------------------------------------------------
    @staticmethod
    def _link_kid(p: DNode, n: DNode, before: Optional[_Kid]) -> None:
        k = _Kid(n)
        n.h, n.up = k, p
        if before is None:
            k.prev = p.kt
            if p.kt is None:
                p.kh = k
            else:
                p.kt.next = k
            p.kt = k
        else:
            k.next, k.prev = before, before.prev
            if before.prev is None:
                p.kh = k
            else:
                before.prev.next = k
            before.prev = k

    @staticmethod
    def _unlink_kid(n: DNode) -> None:
        k, p = n.h, n.up
        if k.prev is None:
            p.kh = k.next
        else:
            k.prev.next = k.next
        if k.next is None:
            p.kt = k.prev
        else:
            k.next.prev = k.prev
        n.h = None

    # -- vertical runs: cut and join from the shorter side ---------------------------------------
    def _cut(self, x: DNode) -> None:
        """x, an only kid in its parent's run, is about to get a sibling or to leave: cut the run
        between x's parent and x; x becomes the top of the lower part. Only the shorter part gets
        a new run object; a part of one vertex needs none (run None)."""
        r = x.run
        top = r.top
        a, b = x.up, x                                # walk both parts in lockstep
        while True:
            if a is top:
                lower = False                         # the upper part is the shorter
                break
            a = a.up
            k = b.kh
            if k is None or k.next is not None:
                lower = True                          # the lower part is the shorter
                break
            b = k.node
        part = []
        if lower:
            m = x
            while True:
                part.append(m)
                k = m.kh
                if k is None or k.next is not None:
                    break
                m = k.node
            new_top = x
        else:
            m = x.up
            while True:
                part.append(m)
                if m is top:
                    break
                m = m.up
            new_top = top
            r.top = x                                 # the lower part keeps r
        new = _Run(new_top, len(part)) if len(part) > 1 else None
        for m in part:
            m.run = new
        r.size -= len(part)
        if r.size == 1:
            r.top.run = None
        self.run_steps += len(part)

    def _join(self, x: DNode) -> None:
        """x has just become an only kid: its run (topped by x) joins its parent's run; the members
        of the smaller run move."""
        p = x.up
        lo, hi = x.run, p.run
        if lo is None:
            lo = x.run = _Run(x)
        if hi is None:
            hi = p.run = _Run(p)
        if lo.size <= hi.size:
            m = x
            while True:
                m.run = hi
                k = m.kh
                if k is None or k.next is not None:
                    break
                m = k.node
            hi.size += lo.size
            self.run_steps += lo.size
        else:
            m, top = p, hi.top
            while True:
                m.run = lo
                if m is top:
                    break
                m = m.up
            lo.size += hi.size
            lo.top = top
            self.run_steps += hi.size

    def _attach(self, p: DNode, n: DNode, before: Optional[_Kid]) -> None:
        """Link n (a new leaf, or a detached subtree topped by n) as a kid of p."""
        if p.kh is not None and p.kh is p.kt:
            self._cut(p.kh.node)                      # p's only kid gets a sibling
        self._link_kid(p, n, before)
        if p.kh is p.kt:
            self._join(n)                             # n is p's only kid

    def _detach(self, n: DNode) -> None:
        """Unlink n (with its subtree) from its parent."""
        p = n.up
        if n.h.prev is None and n.h.next is None:
            self._cut(n)
        self._unlink_kid(n)
        if p.kh is not None and p.kh is p.kt:
            self._join(p.kh.node)                     # one kid left: it joins p's run

    # -- the delimiter -------------------------------------------------------------------------
    def _delimiter(self, n: DNode):
        """The cell just after n's block in Q1: its right sibling's cell, or its parent's
        delimiter (a vertical run is crossed in one step), or SINK above the root."""
        while True:
            h = n.h
            if h is None:
                return self._q.last
            if h.next is not None:
                return h.next.node.c
            n = n.run.top if h.prev is None else n.up
            self.climb_steps += 1

    def _end(self, n: DNode):
        """The last cell of n's block in Q1."""
        return self._delimiter(n).prev

    # -- insertion ------------------------------------------------------------------------------
    def _new(self, name: str, anchor) -> DNode:
        self._check_name(name)
        if name in self._nodes:
            raise ValueError(f"{name!r} is already in the tree")
        n = DNode(name, self)
        n.c = self._q._insert_cell_after(name, anchor)
        n.c.node = n
        self._nodes[name] = n
        return n

    def _parent_for(self, parent, child: str) -> DNode:
        """The parent's handle; the first insertion makes ``parent`` the root."""
        self._check_name(child)
        if self._root is None:
            if isinstance(parent, DNode):
                raise ValueError("the first insert names the root by its name")
            if parent == child:
                raise ValueError(f"{child!r} cannot be its own child")
            self._root = self._new(parent, self._q.first)
            return self._root
        p = self._node(parent)
        if child in self._nodes:
            raise ValueError(f"{child!r} is already in the tree")
        return p

    def insert(self, parent, child: str) -> DNode:
        """Append ``child`` as the last kid of ``parent`` and return its handle. The first call
        makes ``parent`` the root."""
        p = self._parent_for(parent, child)
        n = self._new(child, p.c if p.kh is None else self._end(p))
        self._attach(p, n, None)
        return n

    def insert_first(self, parent, child: str) -> DNode:
        """Insert ``child`` as the first kid of ``parent``: directly after it in Q1."""
        p = self._parent_for(parent, child)
        n = self._new(child, p.c)
        self._attach(p, n, p.kh)
        return n

    def _sibling(self, sibling, child: str) -> DNode:
        self._check_name(child)
        s = self._node(sibling)
        if s.up is None:
            raise ValueError("the root has no siblings")
        if child in self._nodes:
            raise ValueError(f"{child!r} is already in the tree")
        return s

    def insert_before(self, sibling, child: str) -> DNode:
        """Insert ``child`` directly before ``sibling``, under the same parent."""
        s = self._sibling(sibling, child)
        n = self._new(child, s.c.prev)
        self._attach(s.up, n, s.h)
        return n

    def insert_after(self, sibling, child: str) -> DNode:
        """Insert ``child`` directly after ``sibling`` (after its block in Q1), same parent."""
        s = self._sibling(sibling, child)
        n = self._new(child, self._end(s))
        self._attach(s.up, n, s.h.next)
        return n

    # -- changes --------------------------------------------------------------------------------
    def _forget(self, n: DNode) -> None:
        del self._nodes[n.name]
        n.owner = n.up = n.kh = n.kt = n.h = n.c = n.run = None

    def delete(self, node) -> None:
        """Remove ``node``; its kids take its place among its siblings, in order."""
        n = self._node(node)
        if n.up is None:
            raise ValueError("the root cannot be deleted")
        p, k = n.up, n.h
        if k.prev is None and k.next is None:
            self._cut(n)
        if n.kh is not None and n.kh is n.kt:
            self._cut(n.kh.node)
        if n.kh is None:
            self._unlink_kid(n)
        else:
            first, last = n.kh, n.kt
            c = first
            while c is not None:
                c.node.up = p
                c = c.next
            first.prev, last.next = k.prev, k.next          # n's kids take n's place
            if k.prev is None:
                p.kh = first
            else:
                k.prev.next = first
            if k.next is None:
                p.kt = last
            else:
                k.next.prev = last
        if p.kh is not None and p.kh is p.kt:
            self._join(p.kh.node)
        self._q._remove_cell(n.c)
        self._forget(n)

    def delete_subtree(self, node) -> List[str]:
        """Remove ``node`` and all its descendants; returns their names in Q1 order."""
        n = self._node(node)
        if n.up is None:
            raise ValueError("the root cannot be deleted")
        cells = self._q._cut_cells(n.c, self._end(n), forget=True)
        self._detach(n)
        removed = [c.node for c in cells]
        names = [v.name for v in removed]
        for v in removed:
            self._forget(v)
        return names

    def cut_n_paste(self, subtree_root, new_parent) -> None:
        """Move the subtree of ``subtree_root`` under ``new_parent``, as its last kid."""
        u, p = self._node(subtree_root), self._node(new_parent)
        if u.up is None:
            raise ValueError("the root cannot be moved")
        if u is p or self.can_reach(u, p):
            raise ValueError("new_parent lies inside the subtree being moved")
        block = self._q._cut_cells(u.c, self._end(u), forget=False)
        self._detach(u)
        self._q._paste_cells_after(block, p.c if p.kh is None else self._end(p))
        self._attach(p, u, None)

    # -- queries --------------------------------------------------------------------------------
    def can_reach(self, u, v) -> bool:
        """u reaches v (u is a proper ancestor of v). Irreflexive. A cascade of local steps:
        1 v is not right of u, 2 u has no kids, 3 u's right sibling (or the root), 4 u's last kid,
        5 look for the delimiter."""
        u, v = self._node(u), self._node(v)
        if not _lt(u.c, v.c):                # 1
            return False
        if u.kh is None:                     # 2
            return False
        h = u.h
        if h is None:                        # 3: the root, its delimiter is SINK
            return True
        if h.next is not None:               # 3: u's right sibling is its delimiter
            return _lt(v.c, h.next.node.c)
        last = u.kt.node                     # 4: u's last kid
        if not _lt(last.c, v.c):
            return True
        if last.kh is None:                  #    a leaf: its next cell is u's delimiter
            return _lt(v.c, last.c.next)
        return _lt(v.c, self._delimiter(u))  # 5

    def can_not_reach(self, u, v) -> bool:
        return not self.can_reach(u, v)

    def contains(self, node) -> bool:
        return node in self

    def is_ancestor(self, u, v) -> bool:
        return self.can_reach(u, v)

    def is_descendant(self, u, v) -> bool:
        return self.can_reach(v, u)

    def get_parent(self, node) -> Optional[str]:
        up = self._node(node).up
        return None if up is None else up.name

    def children(self, node) -> List[str]:
        return [k.name for k in self._node(node).children]

    def is_root(self, node) -> bool:
        return self._node(node).up is None

    def is_leaf(self, node) -> bool:
        return self._node(node).kh is None

    def depth(self, node) -> int:
        n, d = self._node(node), 0
        while n.up is not None:
            n, d = n.up, d + 1
        return d

    def path_to_root(self, node) -> List[str]:
        n, out = self._node(node), []
        while n is not None:
            out.append(n.name)
            n = n.up
        return out

    def subtree(self, node) -> List[str]:
        """``node`` and its descendants, in Q1 order."""
        n = self._node(node)
        out, c, end = [], n.c, self._delimiter(n)
        while c is not end:
            out.append(c.name)
            c = c.next
        return out

    def subtree_size(self, node) -> int:
        return len(self.subtree(node))

    @property
    def q1(self) -> List[str]:
        """The vertices in Q1 order (pre-order, kids LR)."""
        return list(self._q)

    @property
    def nodes(self) -> List[str]:
        return self.q1

    def __iter__(self) -> Iterator[str]:
        return iter(self._q)

    # -- and/or queries: constructed nodes, built for the query at hand --------------------------
    def vmin(self, nodes: Iterable) -> "VMin":
        return VMin(self, nodes)

    def vmax(self, nodes: Iterable) -> "VMax":
        return VMax(self, nodes)

    def umin(self, nodes: Iterable) -> "UMin":
        return UMin(self, nodes)

    def umax(self, nodes: Iterable) -> "UMax":
        return UMax(self, nodes)


def _by_position(a: DNode, b: DNode) -> int:
    return -1 if _lt(a.c, b.c) else (1 if _lt(b.c, a.c) else 0)


class _Constructed:
    """A set S of vertices reduced to what the query needs, at the moment it is built. Built
    for the query at hand: after the tree changes, build it again."""

    def __init__(self, tree: DTree, nodes: Iterable) -> None:
        self.tree = tree
        members = {}
        for x in nodes:
            n = tree._node(x)
            members[n.name] = n
        if not members:
            raise ValueError("a constructed node needs at least one member")
        self._members = sorted(members.values(), key=cmp_to_key(_by_position))

    @property
    def members(self) -> List[str]:
        """The members in Q1 order."""
        return [m.name for m in self._members]

    def __contains__(self, node) -> bool:
        n = node if isinstance(node, DNode) else self.tree._nodes.get(node)
        return n is not None and any(m is n for m in self._members)

    def __len__(self) -> int:
        return len(self._members)

    @staticmethod
    def _count_before(items: List[DNode], v: DNode) -> int:
        """How many of ``items`` (in Q1 order) lie left of v: a binary search."""
        lo, hi = 0, len(items)
        while lo < hi:
            mid = (lo + hi) // 2
            if _lt(items[mid].c, v.c):
                lo = mid + 1
            else:
                hi = mid
        return lo


class VMin(_Constructed):
    """S as the target: does u reach all of S? u lies left of the first member and its
    delimiter right of the last."""

    def reaches_all(self, u) -> bool:
        u = self.tree._node(u)
        ms = self._members
        return _lt(u.c, ms[0].c) and _lt(ms[-1].c, self.tree._delimiter(u))


class VMax(_Constructed):
    """S as the target: does u reach some of S? The first member after u lies inside u's block."""

    def reaches_some(self, u) -> bool:
        u = self.tree._node(u)
        ms = self._members
        i = self._count_before(ms, u)
        if i < len(ms) and ms[i] is u:
            i += 1
        return i < len(ms) and _lt(u.c, ms[i].c) and _lt(ms[i].c, self.tree._delimiter(u))


class UMax(_Constructed):
    """S as the source: is v reached by all of S? v lies right of the last member and left of
    the first delimiter."""

    def __init__(self, tree: DTree, nodes: Iterable) -> None:
        super().__init__(tree, nodes)
        first = None
        for m in self._members:
            d = tree._delimiter(m)
            if first is None or _lt(d, first):
                first = d
        self._first_delimiter = first

    def reached_by_all(self, v) -> bool:
        v = self.tree._node(v)
        return _lt(self._members[-1].c, v.c) and _lt(v.c, self._first_delimiter)


class UMin(_Constructed):
    """S as the source: is v reached by some of S? Only the topmost members count (those with no
    ancestor in S); their blocks are disjoint, so the last one left of v decides."""

    def __init__(self, tree: DTree, nodes: Iterable) -> None:
        super().__init__(tree, nodes)
        tops, ends, end = [], [], None
        for m in self._members:
            if end is None or not _lt(m.c, end):
                end = tree._delimiter(m)
                tops.append(m)
                ends.append(end)
        self._tops, self._ends = tops, ends

    def covering(self, v) -> Optional[str]:
        """The topmost member that reaches v, or None."""
        v = self.tree._node(v)
        i = self._count_before(self._tops, v)
        if i == 0:
            return None
        return self._tops[i - 1].name if _lt(v.c, self._ends[i - 1]) else None

    def reached_by_some(self, v) -> bool:
        return self.covering(v) is not None
