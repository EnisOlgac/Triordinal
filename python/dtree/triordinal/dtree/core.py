"""DTree: a single-rooted directed tree encoded by two linear projections.

Python implementation of the DTree design and API by Enis Olgac (original C#
prototype in releases up to 1.1.0). This port was written with Claude (Anthropic) and checked against a
brute-force reference in ``tests/``.

Projection model
----------------
Every tree is encoded by two orderings of its nodes, both bracketed by the
symbolic markers SOURCE ("[") and SINK ("]"):

* Q1: pre-order, children left to right (in insertion order).
* Q2: pre-order, children right to left (sibling-reversed).

Node u reaches node v if and only if u strictly precedes v in both Q1 and Q2.
Reachability is irreflexive: no node reaches itself.

Closing cells
-------------
A node with children also has a closing cell in each list, an unnamed cell directly
after the last cell of its subtree (the parent's delimiter of the paper). The subtree
of u is the block from u to its closing cell, in Q1 and in Q2 alike, so the end of a
block is known without any search. Closing cells are not nodes: the projections Q1
and Q2, as seen through ``DTree.Q1`` and ``DTree.Q2``, list the nodes only.

Update rules
------------
* insert(u, v): v is placed directly after u in Q2, and in Q1 directly before u's
  closing cell (created when u gets its first child). O(1); positions of other nodes
  normally stay unchanged.
* insert_after(s, v) / insert_before(s, v): v becomes the next (previous) sibling of s;
  in Q1 it goes after s's closing cell (before s), in Q2 before s (after s's closing cell).
* delete(v): v and its closing cells are removed from both projections; its children
  move up to v's parent and keep their relative order.
* delete_subtree(v): the contiguous block of v's subtree is removed from both
  projections.
* cut_n_paste(u, p): the contiguous block of u's subtree is lifted out of both
  projections and re-inserted under p using the same rule as insert.

Every operation checks its arguments before it changes anything, so an operation that
raises leaves the tree as it was.

Positions are fractions. A new node gets the mediant (a+c)/(b+d) of its two
neighbors a/b and c/d (the Stern-Brocot construction), which always lies
strictly between them, so normally no other node moves. Rational positions
were Enis Olgac's idea; repeated insertion into the same gap (a node with many
children, appending at either end) then keeps positions at O(log n) bits. Only
when a mediant cannot be stored, its denominator or numerator exceeding 2**61, is
a small surrounding region renumbered with simple fractions k/2**20. A subtree
moved by cut_n_paste is placed as one block (see triordinal.dlist).
"""


from __future__ import annotations

from functools import cmp_to_key
from typing import Dict, Iterable, Iterator, List, Optional

from triordinal.dlist import SINK, SOURCE, DList, _Cell


class DNode:
    """Handle of a tree node: refers directly to its positions in Q1 and Q2.

    Returned by ``DTree.insert`` and ``DTree.get_node``. Every DTree method accepts a
    handle wherever it accepts a node name; with handles, ``can_reach`` is two position
    comparisons without any lookup by name. The idea of using addresses as ids comes from
    Enis Olgac's original implementation.
    """

    __slots__ = ("name", "up", "kids", "c1", "c2", "e1", "e2", "owner")

    def __init__(self, name: str, owner: "DTree") -> None:
        self.name = name
        self.up: Optional[DNode] = None      # parent (None for the root)
        self.kids: Optional[List[DNode]] = None  # children in Q1 order
        self.c1: Optional[_Cell] = None      # position in Q1
        self.c2: Optional[_Cell] = None      # position in Q2
        self.e1: Optional[_Cell] = None      # closing cell in Q1 (only while the node has children)
        self.e2: Optional[_Cell] = None      # closing cell in Q2 (likewise)
        self.owner: Optional[DTree] = owner  # None once the node has been removed

    @property
    def parent(self) -> Optional["DNode"]:
        return self.up

    @property
    def children(self) -> List["DNode"]:
        """The children in Q1 order (a copy)."""
        return list(self.kids or ())

    @property
    def is_in_tree(self) -> bool:
        return self.owner is not None

    def __repr__(self) -> str:
        return f"DNode({self.name!r})" if self.owner is not None else f"DNode({self.name!r}, removed)"


def _lt(x: _Cell, y: _Cell) -> bool:
    """x lies strictly left of y; both are cells of nodes or closing cells (never markers)."""
    return x.num * y.den < y.num * x.den


def _reaches(u: DNode, v: DNode) -> bool:
    """u reaches v in two lists: u precedes v in Q1 and in Q2."""
    return _lt(u.c1, v.c1) and _lt(u.c2, v.c2)


def _reaches1(u: DNode, v: DNode) -> bool:
    """u reaches v in one list (EulerTree): v lies strictly inside u's block in Q1."""
    return _lt(u.c1, v.c1) and _lt(v.c1, u.e1 or u.c1)


def _lt2(x: DNode, y: DNode) -> bool:
    """x precedes y in the second coordinate: Q2."""
    return _lt(x.c2, y.c2)


def _lt2_euler(x: DNode, y: DNode) -> bool:
    """x precedes y in the second coordinate of one list: y's block ends before x's block in Q1
    (the block end takes the place of the Q2 position, in reverse order)."""
    return _lt(y.e1 or y.c1, x.e1 or x.c1)


class Projection:
    """Read-only view of Q1 or Q2: the nodes in list order, with the list-level checks of
    DList (is_left_of, index, next, ...). Closing cells are not shown.

    Live: it always reflects the current tree, which changes only through DTree methods.
    """

    __slots__ = ("_list",)

    def __init__(self, dlist: DList) -> None:
        self._list = dlist

    @property
    def name(self) -> str:
        return self._list.name

    @property
    def source(self) -> str:
        return SOURCE

    @property
    def sink(self) -> str:
        return SINK

    @property
    def renumber_count(self) -> int:
        """How often a region of the list was renumbered."""
        return self._list.renumber_count

    @property
    def renumber_moved(self) -> int:
        """How many positions renumbering changed in total (closing cells included)."""
        return self._list.renumber_moved

    @property
    def paste_count(self) -> int:
        """How many pasted blocks (cut_n_paste) fitted into their gap without renumbering."""
        return self._list.paste_count

    def __iter__(self) -> Iterator[str]:
        return iter(self._list)

    def __len__(self) -> int:
        return len(self._list)

    def __contains__(self, name: str) -> bool:
        return name in self._list

    def to_list(self, with_markers: bool = False) -> List[str]:
        return self._list.to_list(with_markers)

    def index(self, name: str):
        """Position of ``name`` as a Fraction (SOURCE/SINK: -inf/+inf), or None if absent."""
        return self._list.index(name)

    label = index

    def is_allocated(self, name: str) -> bool:
        return name in self._list

    def is_not_allocated(self, name: str) -> bool:
        return name not in self._list

    def next(self, name: str) -> Optional[str]:
        return self._list.next(name)

    def prev(self, name: str) -> Optional[str]:
        return self._list.prev(name)

    def is_left_of(self, v: str, u: str) -> bool:
        return self._list.is_left_of(v, u)

    def is_self_or_left_of(self, v: str, u: str) -> bool:
        return self._list.is_self_or_left_of(v, u)

    def is_right_of(self, v: str, u: str) -> bool:
        return self._list.is_right_of(v, u)

    def is_self_or_right_of(self, v: str, u: str) -> bool:
        return self._list.is_self_or_right_of(v, u)

    def precedes(self, u: str, v: str) -> bool:
        return self._list.precedes(u, v)

    def is_same_as(self, other) -> bool:
        """True if both hold the same nodes in the same order (another Projection or a DList)."""
        return list(self) == list(other)

    def __repr__(self) -> str:
        return repr(self._list)


class DTree:
    """Single-rooted directed tree with dual projections Q1 and Q2.

    With ``strict=True``, queries about nodes (can_reach, can_not_reach, is_ancestor,
    is_descendant, is_root and the queries of constructed nodes) raise KeyError for a name
    that is not in the tree or a handle of a removed node, instead of answering False.
    ``contains`` and ``same_subtree`` are membership tests and never raise.
    """

    _single = False  # EulerTree: Q1 only
    _reach = staticmethod(_reaches)
    _lt2 = staticmethod(_lt2)

    def __init__(self, tree_id: str = "P1", strict: bool = False, positions: str = "rational") -> None:
        self.tree_id = tree_id
        self._strict = bool(strict)
        self._nodes: Dict[str, DNode] = {}
        self._root: Optional[DNode] = None
        self._q1 = DList(f"{tree_id}.Q1", positions)
        self._v1 = Projection(self._q1)
        if self._single:
            self._q2 = self._v2 = None
        else:
            self._q2 = DList(f"{tree_id}.Q2", positions)
            self._v2 = Projection(self._q2)
        self.edge_log: List[str] = []
        self._reshapes = 0  # counts deletions and moves; insertions keep the order of existing nodes

    @property
    def positions(self) -> str:
        """The kind of position in the lists: "rational" (the default) or "integer"."""
        return self._q1.positions

    @property
    def strict(self) -> bool:
        """Whether queries raise KeyError for unknown nodes (set at construction)."""
        return self._strict

    # -- construction ------------------------------------------------------
    @classmethod
    def from_file(cls, path: str, tree_id: Optional[str] = None, strict: bool = False,
                  positions: str = "rational") -> "DTree":
        """Read the format used by the .csx examples.

        ``parent: child1; child2`` adds children as last children of ``parent``;
        ``sibling > child1; child2`` inserts them as siblings directly after ``sibling``
        (in that order), ``sibling < child1; child2`` directly before it. Empty lines and
        lines starting with ``#``, ``--`` or ``**`` are skipped, ``@@`` ends the description;
        any other line without ``:``, ``>`` or ``<`` raises ValueError.
        """
        import os

        tree = cls(tree_id or os.path.splitext(os.path.basename(path))[0], strict, positions)
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
        """Apply one line of the description format (see from_file); returns the new handles.

        The children are added one by one; if one of them is rejected, those before it
        remain in the tree.
        """
        at = min((i for i in (line.find(":"), line.find(">"), line.find("<")) if i >= 0), default=-1)
        if at < 0:
            raise ValueError(f"no ':', '>' or '<' in {line!r}")
        op, anchor = line[at], line[:at].strip()
        children = [c.strip() for c in line[at + 1:].split(";") if c.strip()]
        added = []
        for child in children:
            if op == ":":
                added.append(self.insert(anchor, child))
            elif op == ">":
                added.append(self.insert_after(anchor, child))
                anchor = child                       # the next one goes after this one
            else:
                added.append(self.insert_before(anchor, child))
        return added

    @staticmethod
    def _check_name(name) -> None:
        if not isinstance(name, str):
            raise TypeError(f"a node name must be a string, not {type(name).__name__}")
        if not name:
            raise ValueError("a node name must not be empty")
        if name in (SOURCE, SINK):
            raise ValueError("SOURCE/SINK markers cannot be tree nodes")

    def insert(self, parent, child: str) -> DNode:
        """Add the edge parent -> child and return the handle of ``child``.

        ``parent`` is a name or a handle. The first call makes ``parent`` the root.
        Afterwards ``parent`` must already exist and ``child`` must not.
        """
        self._check_name(child)
        if self._root is None:
            if isinstance(parent, DNode):
                raise ValueError("the first insert names the root by its name")
            self._check_name(parent)
            if parent == child:
                raise ValueError(f"child {child!r} is already in the tree")
            p = self._make_root(parent)
        else:
            p = self._node(parent)
            if child in self._nodes:
                raise ValueError(f"child {child!r} is already in the tree")
        self._open(p)
        n = self._attach(child, p, None, p.e1.prev, p.c2)    # Q1 before p's closing cell, Q2 after p
        self.edge_log.append(f"({p.name}, {child})")
        return n

    def insert_after(self, sibling, child: str) -> DNode:
        """Insert ``child`` as a sibling directly after ``sibling`` (same parent) and return its
        handle. In Q1 it goes after the end of the sibling's subtree, in Q2 directly before the
        sibling; no other node moves. The root has no siblings."""
        s = self._sibling(sibling, child)
        p = s.up
        i = p.kids.index(s)
        n = self._attach(child, p, i + 1, s.e1 or s.c1, None if self._single else s.c2.prev)
        self.edge_log.append(f"({s.name} > {child})")
        return n

    def insert_before(self, sibling, child: str) -> DNode:
        """Insert ``child`` as a sibling directly before ``sibling`` (same parent) and return its
        handle. In Q1 it goes directly before the sibling, in Q2 after the end of the sibling's
        subtree there (its closing cell); no other node moves."""
        s = self._sibling(sibling, child)
        p = s.up
        i = p.kids.index(s)
        n = self._attach(child, p, i, s.c1.prev, s.e2 or s.c2)
        self.edge_log.append(f"({s.name} < {child})")
        return n

    def _sibling(self, sibling, child: str) -> DNode:
        self._check_name(child)
        s = self._node(sibling)
        if s.up is None:
            raise ValueError("the root has no siblings")
        if child in self._nodes:
            raise ValueError(f"child {child!r} is already in the tree")
        return s

    def _make_root(self, name: str) -> DNode:
        n = DNode(name, self)
        n.c1 = self._q1._insert_cell_after(name, self._q1.first)
        n.c1.node = n
        if not self._single:
            n.c2 = self._q2._insert_cell_after(name, self._q2.first)
            n.c2.node = n
        self._root = n
        self._nodes[name] = n
        return n

    def _attach(self, name: str, p: DNode, index: Optional[int], q1_after: _Cell, q2_after: _Cell) -> DNode:
        """Create a child of p at position ``index`` among p's children (None: last), linked
        after the given cells. All checks are done; the name is registered last."""
        n = DNode(name, self)
        n.c1 = self._q1._insert_cell_after(name, q1_after)
        n.c1.node = n
        if not self._single:
            n.c2 = self._q2._insert_cell_after(name, q2_after)
            n.c2.node = n
        n.up = p
        if p.kids is None:
            p.kids = [n]
        elif index is None:
            p.kids.append(n)
        else:
            p.kids.insert(index, n)
        self._nodes[name] = n
        return n

    # -- closing cells -----------------------------------------------------
    def _open(self, p: DNode) -> None:
        """Give p its closing cells if it has none: directly after p, as its block is p alone."""
        if p.e1 is None:
            p.e1 = self._q1._insert_cell_after(None, p.c1)
            p.e1.node = p
            if not self._single:
                p.e2 = self._q2._insert_cell_after(None, p.c2)
                p.e2.node = p

    def _close(self, p: DNode) -> None:
        """Remove p's closing cells once p has no children left."""
        if p.e1 is not None:
            self._q1._remove_cell(p.e1)
            if not self._single:
                self._q2._remove_cell(p.e2)
            p.e1 = p.e2 = None

    def _in(self, p: DNode, x: DNode) -> bool:
        """x is p or lies in p's subtree."""
        return x is p or self._reach(p, x)

    def next_in_q1(self, node) -> Optional[str]:
        """The node after ``node`` in Q1, as a name, or None after the last node. Q1 is the
        display order of a tree view (parents before children, siblings in insertion order).
        Passes over the closing cells of the subtrees that end after ``node``: O(1) amortized
        over a walk through Q1."""
        c = self._node(node).c1.next
        while c.name is None:
            c = c.next
        return None if c is self._q1.last else c.name

    def subtree_last(self, node):
        """Last node of the subtree of ``node`` in Q1, as a name (the subtree is the block from
        ``node`` to it). Goes back from the closing cell of ``node`` over the closing cells that
        precede it: O(length of the path of last children below ``node``)."""
        c = self._end1(self._node(node))
        while c.name is None:
            c = c.prev
        return c.name

    @staticmethod
    def _end1(n: DNode) -> _Cell:
        return n.e1 or n.c1

    @staticmethod
    def _end2(n: DNode) -> _Cell:
        return n.e2 or n.c2

    # -- structural reconfiguration ---------------------------------------
    def delete(self, node) -> None:
        """Remove ``node``; its children are re-attached to its parent.

        Deleting the root is disallowed.
        """
        n = self._node(node)
        if n is self._root:
            raise ValueError("the root cannot be deleted")
        p = n.up
        kids = n.kids or []
        i = p.kids.index(n)
        p.kids[i : i + 1] = kids
        for k in kids:
            k.up = p
        self._q1._remove_cell(n.c1)
        if not self._single:
            self._q2._remove_cell(n.c2)
        self._close(n)
        if not p.kids:
            p.kids = None
            self._close(p)
        self._forget(n)
        self._reshapes += 1

    def delete_subtree(self, node) -> List[str]:
        """Remove ``node`` together with all its descendants.

        Returns the removed nodes in Q1 order. Deleting the root's subtree
        (the whole tree) is disallowed, as for delete.
        """
        n = self._node(node)
        if n is self._root:
            raise ValueError("the root cannot be deleted")
        cells = self._q1._cut_cells(n.c1, self._end1(n), forget=True)
        if not self._single:
            self._q2._cut_cells(n.c2, self._end2(n), forget=True)
        removed = [c.node for c in cells if c.name is not None]
        p = n.up
        p.kids.remove(n)
        if not p.kids:
            p.kids = None
            self._close(p)
        for v in removed:
            self._forget(v)
        self._reshapes += 1
        return [v.name for v in removed]

    def cut_n_paste(self, subtree_root, new_parent) -> None:
        """Detach the subtree rooted at ``subtree_root`` and attach it under ``new_parent``.

        The subtree keeps its internal shape and becomes the last child of
        ``new_parent``. ``new_parent`` must not lie inside the moved subtree,
        and the root cannot be moved. Handles stay valid.
        """
        u = self._node(subtree_root)
        p = self._node(new_parent)
        if u is self._root:
            raise ValueError("the root cannot be moved")
        if self._in(u, p):
            raise ValueError("new_parent lies inside the subtree being moved")
        block1 = self._q1._cut_cells(u.c1, self._end1(u), forget=False)
        block2 = None if self._single else self._q2._cut_cells(u.c2, self._end2(u), forget=False)
        old = u.up
        old.kids.remove(u)
        if not old.kids:
            old.kids = None
            self._close(old)
        # Same placement rule as insert: Q2 directly after the parent,
        # Q1 directly before the parent's closing cell.
        self._open(p)
        if not self._single:
            self._q2._paste_cells_after(block2, p.c2)
        self._q1._paste_cells_after(block1, p.e1.prev)
        u.up = p
        if p.kids is None:
            p.kids = [u]
        else:
            p.kids.append(u)
        self._reshapes += 1

    def _forget(self, n: DNode) -> None:
        del self._nodes[n.name]
        n.owner = None
        n.up = n.kids = None
        n.e1 = n.e2 = None

    # -- handles and names -------------------------------------------------
    def get_node(self, name: str) -> DNode:
        """Handle of the node called ``name``. Raises KeyError if absent."""
        n = self._nodes.get(name)
        if n is None:
            raise KeyError(f"node {name!r} is not in the tree")
        return n

    def try_get_node(self, name: str) -> Optional[DNode]:
        return self._nodes.get(name)

    def _node(self, x) -> DNode:
        """Resolve a name or a handle of this tree; raises KeyError otherwise."""
        if x.__class__ is DNode:
            if x.owner is not self:
                raise KeyError(f"node {x.name!r} is not in this tree")
            return x
        n = self._nodes.get(x)
        if n is None:
            raise KeyError(f"node {x!r} is not in the tree")
        return n

    def _lookup(self, x) -> Optional[DNode]:
        """Resolve a name or handle for a query: None if it is not in the tree (strict: KeyError)."""
        if x.__class__ is DNode:
            if x.owner is self:
                return x
        else:
            n = self._nodes.get(x)
            if n is not None:
                return n
        if self._strict:
            self._node(x)                                   # raises the KeyError
        return None

    def _missing(self, x) -> bool:
        """Answer of a query about an unknown node: False, or KeyError in strict mode."""
        if self._strict:
            self._node(x)
        return False

    # -- accessors --------------------------------------------------------
    @property
    def root(self) -> Optional[str]:
        return self._root.name if self._root is not None else None

    @property
    def source(self) -> str:
        return SOURCE

    @property
    def sink(self) -> str:
        return SINK

    @property
    def Q1(self) -> Projection:
        """Read-only view of the Q1 projection, for list-level checks (is_left_of, index, ...)."""
        return self._v1

    @property
    def Q2(self) -> Projection:
        """Read-only view of the Q2 projection, as Q1."""
        if self._single:
            raise AttributeError("an EulerTree keeps Q1 only; it has no Q2")
        return self._v2

    @property
    def q1(self) -> List[str]:
        """Q1 as a plain list of node names (a copy, without the markers)."""
        return self._q1.to_list()

    @property
    def q2(self) -> List[str]:
        if self._single:
            raise AttributeError("an EulerTree keeps Q1 only; it has no Q2")
        return self._q2.to_list()

    @property
    def size(self) -> int:
        return len(self._nodes)

    @property
    def nodes(self) -> List[str]:
        return self.q1

    @property
    def _parent(self) -> Dict[str, str]:
        """child name -> parent name (root -> SOURCE); a snapshot, e.g. for comparisons."""
        return {n.name: (n.up.name if n.up is not None else SOURCE) for n in self._nodes.values()}

    def __len__(self) -> int:
        return self.size

    def __contains__(self, node) -> bool:
        return self.contains(node)

    def __repr__(self) -> str:
        lists = f"\n  {self._q1!r}" + ("" if self._single else f"\n  {self._q2!r}")
        return f"{type(self).__name__}({self.tree_id!r}, size={self.size}){lists}"

    # -- queries ----------------------------------------------------------
    def contains(self, node) -> bool:
        if node.__class__ is DNode:
            return node.owner is self
        return node in self._nodes

    def get_parent(self, node) -> Optional[str]:
        """Parent of ``node``; ``None`` for the root. Raises KeyError if absent."""
        p = self._node(node).up
        return p.name if p is not None else None

    def children(self, node) -> List[str]:
        """The children of ``node`` in Q1 order."""
        return [k.name for k in (self._node(node).kids or ())]

    def can_reach(self, u, v) -> bool:
        """True if there is a directed path of length >= 1 from u to v (names or handles).

        Irreflexive: can_reach(u, u) is False. With handles: two position comparisons.
        A node not in the tree reaches nothing and is reached by nothing; in strict mode
        it raises KeyError instead.
        """
        if u.__class__ is DNode:
            if u.owner is not self:
                return self._missing(u)
        else:
            a = self._nodes.get(u)
            if a is None:
                return self._missing(u)
            u = a
        if v.__class__ is DNode:
            if v.owner is not self:
                return self._missing(v)
        else:
            b = self._nodes.get(v)
            if b is None:
                return self._missing(v)
            v = b
        a, b = u.c1, v.c1
        if not a.num * b.den < b.num * a.den:
            return False
        if self._single:                                   # one list: v's cell before u's block ends
            a, b = b, u.e1 or a
        else:
            a, b = u.c2, v.c2
        return a.num * b.den < b.num * a.den

    def can_not_reach(self, u, v) -> bool:
        return not self.can_reach(u, v)

    def is_root(self, node) -> bool:
        n = self._lookup(node)
        return n is not None and n is self._root

    def is_leaf(self, node) -> bool:
        return not self._node(node).kids

    def is_ancestor(self, u, v) -> bool:
        """True if u is a proper ancestor of v (u lies above v on v's root path)."""
        return self.can_reach(u, v)

    def is_descendant(self, u, v) -> bool:
        """True if u lies below v. Equivalent to is_ancestor(v, u)."""
        return self.can_reach(v, u)

    def same_subtree(self, u, v) -> bool:
        """True if both nodes are in this tree (and so share its root)."""
        return self.contains(u) and self.contains(v)

    def subtree(self, node) -> List[str]:
        """Nodes of the subtree rooted at ``node``, in Q1 order."""
        n = self._node(node)
        out, c, end = [n.name], n.c1, self._end1(n)
        while c is not end:
            c = c.next
            if c.name is not None:
                out.append(c.name)
        return out

    def subtree_size(self, node) -> int:
        return len(self.subtree(node))

    def path_to_root(self, node) -> List[str]:
        """[node, parent, ..., root]."""
        out, w = [], self._node(node)
        while w is not None:
            out.append(w.name)
            w = w.up
        return out

    def root_to_path(self, node) -> List[str]:
        """[root, ..., parent, node]."""
        return self.path_to_root(node)[::-1]

    def path(self, u, v) -> List[str]:
        """Nodes from u down to v, both included; [u] when u == v.

        Raises if u != v and u cannot reach v.
        """
        a, b = self._node(u), self._node(v)
        if a is not b and not self._reach(a, b):
            raise ValueError(f"{a.name!r} cannot reach {b.name!r}")
        out, w = [b.name], b
        while w is not a:
            w = w.up
            out.append(w.name)
        return out[::-1]

    def depth(self, node) -> int:
        """Distance from the root; the root has depth 0."""
        d, w = 0, self._node(node).up
        while w is not None:
            d += 1
            w = w.up
        return d

    # -- and/or queries on the topology -----------------------------------
    def vmin(self, nodes: Iterable = ()) -> "VMin":
        """Constructed node VMin: the minimum of each index over the nodes (see VMin)."""
        return VMin(self, nodes)

    def vmax(self, nodes: Iterable = ()) -> "VMax":
        """Constructed node VMax: the maximum of each index over the nodes (see VMax)."""
        return VMax(self, nodes)

    def umin(self, nodes: Iterable = ()) -> "UMin":
        """Constructed node UMin: the minimum of each index over the nodes (see UMin)."""
        return UMin(self, nodes)

    def umax(self, nodes: Iterable = ()) -> "UMax":
        """Constructed node UMax: the maximum of each index over the nodes (see UMax)."""
        return UMax(self, nodes)


def _q1_order(a: DNode, b: DNode) -> int:
    return -1 if _lt(a.c1, b.c1) else (1 if _lt(b.c1, a.c1) else 0)


class _VNode:
    """A constructed node for a set S of tree nodes (E. Olgac, "Topology and Structure of
    Directed Graphs - Inducing a Subgraph", 2021): the minimum (VMin, UMin) or maximum
    (VMax, UMax) of each index over S. V means S takes the target role, can_reach(u, S),
    and U the source role, can_reach(S, v); UMin and VMin hold the same numbers.

    It stores no positions, only the members (as node handles) and, for each of Q1 and Q2,
    the member holding the minimal (or maximal) index there; the two may be different nodes,
    so the constructed node usually corresponds to no real node. Insertions and renumbering
    keep the order of existing nodes, so it stays valid while the tree grows. After a deletion
    or a cut_n_paste it is recomputed from the remaining members on its next use; a member
    that was deleted is dropped, even if a new node with the same name is inserted later.
    Members are added with ``add`` and removed with ``discard``.
    """

    _lowest = True  # VMin keeps the leftmost member, VMax the rightmost

    def __init__(self, tree: "DTree", nodes: Iterable = ()) -> None:
        self._t = tree
        self._members: List[DNode] = []    # in Q1 order
        self._seen: set = set()
        self._c1: Optional[DNode] = None
        self._c2: Optional[DNode] = None
        self._reshapes = tree._reshapes
        for v in nodes:
            self.add(v)

    def _better1(self, v: DNode, c: Optional[DNode]) -> bool:
        return c is None or (_lt(v.c1, c.c1) if self._lowest else _lt(c.c1, v.c1))

    def _better2(self, v: DNode, c: Optional[DNode]) -> bool:
        lt2 = self._t._lt2
        return c is None or (lt2(v, c) if self._lowest else lt2(c, v))

    def _rescan(self) -> None:
        self._c1 = self._c2 = None
        for v in self._members:
            if self._better1(v, self._c1):
                self._c1 = v
            if self._better2(v, self._c2):
                self._c2 = v

    def _first_not_left_of(self, n: DNode) -> int:
        """Number of members strictly left of n in Q1."""
        m, lo, hi = self._members, 0, len(self._members)
        while lo < hi:
            mid = (lo + hi) // 2
            if _lt(m[mid].c1, n.c1):
                lo = mid + 1
            else:
                hi = mid
        return lo

    def add(self, node) -> "_VNode":
        """Add a node of the tree (name or handle) to the set; returns the constructed node itself.
        Raises KeyError if the node is not in the tree."""
        n = self._t._node(node)
        self._check()
        if n in self._seen:
            return self
        self._seen.add(n)
        self._members.insert(self._first_not_left_of(n), n)   # keep members in Q1 order
        if self._better1(n, self._c1):
            self._c1 = n
        if self._better2(n, self._c2):
            self._c2 = n
        self._added(n)
        return self

    def discard(self, node) -> "_VNode":
        """Remove a node (name or handle) from the set; no error if it is not a member.

        O(log k) to find it plus the list removal; if it held an index (the minimal or
        maximal position in Q1 or Q2), the index nodes are recomputed in O(k). Returns the
        constructed node itself. Typical use: expanding a node in a tree view, after it was
        added to the set of collapsed nodes.
        """
        self._check()
        n = node if node.__class__ is DNode else self._t.try_get_node(node)
        if n is None or n not in self._seen:
            return self
        self._seen.discard(n)
        del self._members[self._first_not_left_of(n)]
        if n is self._c1 or n is self._c2:
            self._rescan()
        self._discarded(n)
        return self

    def __contains__(self, node) -> bool:
        self._check()
        n = node if node.__class__ is DNode else self._t.try_get_node(node)
        return n is not None and n in self._seen

    def _added(self, node: DNode) -> None:
        """Hook for subclasses that keep more than the index nodes."""

    def _discarded(self, node: DNode) -> None:
        """Hook for subclasses that keep more than the index nodes."""

    def _rebuilt(self) -> None:
        """Hook for subclasses that keep more than the index nodes."""

    def refresh(self) -> None:
        """Drop deleted members and recompute the index nodes."""
        t = self._t
        self._members = sorted((v for v in self._members if v.owner is t), key=cmp_to_key(_q1_order))
        self._seen = set(self._members)
        self._rescan()
        self._reshapes = t._reshapes
        self._rebuilt()

    def _check(self) -> None:
        if self._reshapes != self._t._reshapes:
            self.refresh()

    def _query(self, x) -> Optional[DNode]:
        """The node asked about, after the set is brought up to date; None if not in the tree."""
        self._check()
        return self._t._lookup(x)

    @property
    def members(self) -> List[str]:
        """The members' names, in Q1 order."""
        self._check()
        return [v.name for v in self._members]

    @property
    def index_nodes(self) -> tuple:
        """The members holding the minimal (VMin, UMin) or maximal (VMax, UMax) index in Q1 and in Q2 (possibly two different nodes)."""
        self._check()
        return (self._c1.name if self._c1 else None, self._c2.name if self._c2 else None)

    def __len__(self) -> int:
        self._check()
        return len(self._members)

    def _below(self, u: DNode) -> bool:
        """u lies strictly left of the constructed node in both Q1 and Q2."""
        return _lt(u.c1, self._c1.c1) and self._t._lt2(u, self._c2)

    def _above(self, v: DNode) -> bool:
        """v lies strictly right of the constructed node in both Q1 and Q2."""
        return _lt(self._c1.c1, v.c1) and self._t._lt2(self._c2, v)


class VMin(_VNode):
    """S in the target role, can_reach(u, S). Minimum of each index over a node set: u reaches all of the set exactly when u lies
    strictly left of VMin in both Q1 and Q2."""

    _lowest = True

    def reaches_all(self, u) -> bool:
        """True if u reaches every node of the set (vacuously True for an empty set)."""
        n = self._query(u)
        if n is None:
            return False
        return self._c1 is None or self._below(n)


class VMax(_VNode):
    """S in the target role, can_reach(u, S). Maximum of each index over a node set: lying
    strictly left of VMax in both Q1 and Q2 is necessary for u to reach some of the set, but
    not sufficient, so may_reach_some is only a filter; reaches_some is exact."""

    _lowest = False

    def may_reach_some(self, u) -> bool:
        """Fast rejection: False means u reaches no node of the set. True is not a confirmation."""
        n = self._query(u)
        return n is not None and self._c1 is not None and self._below(n)

    def reaches_some(self, u) -> bool:
        """True if u reaches at least one node of the set (exact).

        The subtree of u is the block directly after u in Q1, so u reaches some member
        exactly when the first member after u in Q1 lies in it: a binary search over the
        members (kept in Q1 order) and one reachability test.
        """
        n = self._query(u)
        if n is None or self._c1 is None or not self._below(n):
            return False
        m, lo, hi = self._members, 0, len(self._members)
        while lo < hi:
            mid = (lo + hi) // 2
            if _lt(n.c1, m[mid].c1):
                hi = mid
            else:
                lo = mid + 1
        return lo < len(m) and self._t._reach(n, m[lo])


class UMax(_VNode):
    """S in the source role, can_reach(S, v). Maximum of each index over a node set: v is
    reached by all of the set exactly when v lies strictly right of UMax in both Q1 and Q2."""

    _lowest = False

    def reached_by_all(self, v) -> bool:
        """True if every node of the set reaches v (vacuously True for an empty set)."""
        n = self._query(v)
        if n is None:
            return False
        return self._c1 is None or self._above(n)


class UMin(_VNode):
    """S in the source role, can_reach(S, v). Minimum of each index over a node set: lying
    strictly right of UMin in both Q1 and Q2 is necessary for v to be reached by some of the
    set, but not sufficient, so may_be_reached_by_some is only a filter; reached_by_some is
    exact.

    The exact test keeps the topmost members (those with no ancestor in the set) in Q1
    order. Their subtrees are disjoint, so if one of them is an ancestor of v, no other
    topmost member lies between it and v in Q1: the last topmost member before v in Q1 is
    the only one to test.
    """

    _lowest = True

    def __init__(self, tree: "DTree", nodes: Iterable = ()) -> None:
        self._tops: List[DNode] = []       # topmost members, in Q1 order
        super().__init__(tree, nodes)

    def _last_top_before(self, v: DNode) -> int:
        """Number of topmost members strictly left of v in Q1."""
        m, lo, hi = self._tops, 0, len(self._tops)
        while lo < hi:
            mid = (lo + hi) // 2
            if _lt(m[mid].c1, v.c1):
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _cover(self, v: DNode) -> Optional[DNode]:
        i = self._last_top_before(v)
        if i > 0 and self._t._reach(self._tops[i - 1], v):
            return self._tops[i - 1]
        return None

    def _added(self, node: DNode) -> None:
        if self._cover(node) is not None:
            return                       # an ancestor of node is already in the set
        i = self._last_top_before(node)
        m = self._tops
        while i < len(m) and self._t._reach(node, m[i]):
            del m[i]                     # node is above them: they are no longer topmost
        m.insert(i, node)

    def _discarded(self, node: DNode) -> None:
        if node in self._tops:           # members it covered may become topmost
            self._rebuilt()

    def _rebuilt(self) -> None:
        self._tops = []
        for v in self._members:          # Q1 order: ancestors come first
            if not (self._tops and self._t._reach(self._tops[-1], v)):
                self._tops.append(v)

    def may_be_reached_by_some(self, v) -> bool:
        """Fast rejection: False means no node of the set reaches v; True is not a confirmation."""
        n = self._query(v)
        return n is not None and self._c1 is not None and self._above(n)

    def reached_by_some(self, v) -> bool:
        """True if at least one node of the set reaches v (exact, O(log k))."""
        n = self._query(v)
        if n is None or self._c1 is None or not self._above(n):
            return False
        return self._cover(n) is not None

    def covering(self, v) -> Optional[str]:
        """The topmost member of the set that reaches v, or None if no member does (O(log k)).

        With the collapsed nodes of a tree view as a UMin, this is the visible row that
        contains v: None means v itself is visible.
        """
        n = self._query(v)
        if n is None:
            return None
        c = self._cover(n)
        return c.name if c is not None else None
