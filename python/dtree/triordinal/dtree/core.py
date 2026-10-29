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

Update rules (taken from the C# original)
----------------------------------------
* insert(u, v): v is placed immediately after u in Q2, and in Q1 immediately
  before the first node after u that u cannot reach (the end of u's subtree).
  Insertion costs O(depth of the subtree below u); positions of other nodes
  normally stay unchanged.
* delete(v): v is removed from both projections; its children move up to v's
  parent and keep their relative order (a cut-and-paste of v's children).
* delete_subtree(v): the contiguous block of v's subtree is removed from both
  projections.
* cut_n_paste(u, p): the contiguous block of u's subtree is lifted out of both
  projections and re-inserted under p using the same rule as insert.

Positions are fractions. A new node gets the mediant (a+c)/(b+d) of its two
neighbors a/b and c/d (the Stern-Brocot construction), which always lies
strictly between them, so normally no other node moves. Rational positions
were Enis Olgac's idea; repeated insertion into the same gap (a node with many
children, appending at either end) then keeps positions at O(log n) bits. Only
when a denominator would exceed 64 bits, which needs alternating insertions,
is a small surrounding region renumbered with simple fractions k/2**32.
"""


from __future__ import annotations
from typing import Dict, Iterable, Iterator, List, Optional

from triordinal.dlist import SINK, SOURCE, DList, _Cell


class DNode:
    """Handle of a tree node: refers directly to its positions in Q1 and Q2.

    Returned by ``DTree.insert`` and ``DTree.get_node``. Every DTree method accepts a
    handle wherever it accepts a node name; with handles, ``can_reach`` is two position
    comparisons without any lookup by name. The idea of using addresses as ids comes from
    Enis Olgac's original implementation.
    """

    __slots__ = ("name", "up", "kids", "c1", "c2", "last", "owner")

    def __init__(self, name: str, owner: "DTree") -> None:
        self.name = name
        self.up: Optional[DNode] = None      # parent (None for the root)
        self.kids: Optional[List[DNode]] = None
        self.c1: Optional[_Cell] = None      # position in Q1
        self.c2: Optional[_Cell] = None      # position in Q2
        self.last: Optional[DNode] = None    # hint: last node of the subtree in Q1 (validated before use)
        self.owner: Optional[DTree] = owner  # None once the node has been removed

    @property
    def parent(self) -> Optional["DNode"]:
        return self.up

    @property
    def children(self) -> List["DNode"]:
        return list(self.kids or ())

    @property
    def is_in_tree(self) -> bool:
        return self.owner is not None

    def __repr__(self) -> str:
        return f"DNode({self.name!r})" if self.owner is not None else f"DNode({self.name!r}, removed)"


_BUDGET = 8  # steps of the plain walk to the end of a subtree before the validated hint is used


class DTree:
    """Single-rooted directed tree with dual projections Q1 and Q2."""

    def __init__(self, tree_id: str = "P1") -> None:
        self.tree_id = tree_id
        self._nodes: Dict[str, DNode] = {}
        self._root: Optional[DNode] = None
        self._q1 = DList(f"{tree_id}.Q1")
        self._q2 = DList(f"{tree_id}.Q2")
        self.edge_log: List[str] = []
        self._reshapes = 0  # counts deletions and moves; insertions keep the order of existing nodes

    # -- construction ------------------------------------------------------
    @classmethod
    def from_file(cls, path: str, tree_id: Optional[str] = None) -> "DTree":
        """Read the format used by the .csx examples.

        ``parent: child1; child2`` adds children as last children of ``parent``;
        ``sibling > child1; child2`` inserts them as siblings directly after ``sibling``
        (in that order), ``sibling < child1; child2`` directly before it.
        """
        import os

        tree = cls(tree_id or os.path.splitext(os.path.basename(path))[0])
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
        """Apply one line of the description format (see from_file); returns the new handles."""
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

    def insert(self, parent, child: str) -> DNode:
        """Add the edge parent -> child and return the handle of ``child``.

        ``parent`` is a name or a handle. The first call makes ``parent`` the root.
        Afterwards ``parent`` must already exist and ``child`` must not.
        """
        if child in (SOURCE, SINK) or (isinstance(parent, str) and parent in (SOURCE, SINK)):
            raise ValueError("SOURCE/SINK markers cannot be tree nodes")
        if self._root is None:
            if isinstance(parent, DNode):
                raise ValueError("the first insert names the root by its name")
            self._root = self._new_node(parent, None)
        p = self._node(parent)
        if child in self._nodes:
            raise ValueError(f"child {child!r} is already in the tree")
        n = self._new_node(child, p)
        self.edge_log.append(f"({p.name}, {child})")
        return n

    def insert_after(self, sibling, child: str) -> DNode:
        """Insert ``child`` as a sibling directly after ``sibling`` (same parent) and return its
        handle. In Q1 it goes after the end of the sibling's subtree, in Q2 directly before the
        sibling; no other node moves. The root has no siblings."""
        s = self._sibling(sibling, child)
        p = s.up
        i = p.kids.index(s)
        w = self._subtree_last_node(s)
        n = self._link_node(child, p, i + 1, w.c1, s.c2.prev)
        if i + 1 == len(p.kids) - 1:
            p.last = n                                  # n is now the last node of p's subtree
        self.edge_log.append(f"({s.name} > {child})")
        return n

    def insert_before(self, sibling, child: str) -> DNode:
        """Insert ``child`` as a sibling directly before ``sibling`` (same parent) and return its
        handle. In Q1 it goes directly before the sibling, in Q2 after the end of the sibling's
        subtree there (directly before the previous sibling; for a first child, after the end
        of the parent's subtree in Q2, found by following first children); no other node moves."""
        s = self._sibling(sibling, child)
        p = s.up
        i = p.kids.index(s)
        q2_after = p.kids[i - 1].c2.prev if i > 0 else self._subtree_first_last_q2(s).c2
        n = self._link_node(child, p, i, s.c1.prev, q2_after)
        self.edge_log.append(f"({s.name} < {child})")
        return n

    def _sibling(self, sibling, child: str) -> DNode:
        if child in (SOURCE, SINK):
            raise ValueError("SOURCE/SINK markers cannot be tree nodes")
        s = self._node(sibling)
        if s.up is None:
            raise ValueError("the root has no siblings")
        if child in self._nodes:
            raise ValueError(f"child {child!r} is already in the tree")
        return s

    def _link_node(self, name: str, p: DNode, index: int, q1_after, q2_after) -> DNode:
        """Create a child of p at position ``index`` among p's children, linked after the given cells."""
        n = DNode(name, self)
        c1, c2 = self._q1._new(name), self._q2._new(name)
        self._q2._link_after(c2, q2_after)
        self._q1._link_after(c1, q1_after)
        n.up = p
        p.kids.insert(index, n)
        c1.node = c2.node = n
        n.c1, n.c2 = c1, c2
        self._nodes[name] = n
        return n

    def _new_node(self, name: str, p: Optional[DNode]) -> DNode:
        n = DNode(name, self)
        q1, q2 = self._q1, self._q2
        if p is None:                                   # the root
            c1, c2 = q1._new(name), q2._new(name)
            q1._link_after(c1, q1.first)
            q2._link_after(c2, q2.first)
        else:
            w = self._subtree_last_node(p)              # Q1: after the end of p's subtree
            c2 = q2._new(name)                          # Q2: right after p
            q2._link_after(c2, p.c2)
            c1 = q1._new(name)
            q1._link_after(c1, w.c1)
            n.up = p
            if p.kids is None:
                p.kids = [n]
            else:
                p.kids.append(n)
            p.last = n                                  # n is now the last node of p's subtree
        c1.node = c2.node = n
        n.c1, n.c2 = c1, c2
        self._nodes[name] = n
        return n

    # -- the end of a subtree in Q1 ---------------------------------------
    @staticmethod
    def _in(p: DNode, x: DNode) -> bool:
        """x is p or lies in p's subtree."""
        if x is p:
            return True
        a, b = p.c1, x.c1
        if not a.num * b.den < b.num * a.den:
            return False
        a, b = p.c2, x.c2
        return a.num * b.den < b.num * a.den

    def _is_last(self, p: DNode, x: Optional[DNode]) -> bool:
        """x is the last node of p's subtree in Q1: x lies in it and x's Q1 successor does not."""
        if x is None or x.owner is not self or not self._in(p, x):
            return False
        nxt = x.c1.next
        return nxt.den == 0 or not self._in(p, nxt.node)

    def _subtree_last_node(self, p: DNode) -> DNode:
        """Last node of p's subtree in Q1.

        A short walk down the last children finds it on ordinary trees. Beyond _BUDGET steps,
        the end remembered last time (p.last) is used if it validates in O(1); otherwise the
        walk continues, stops at a node whose own hint validates, and every node passed gets
        the found end as its new hint (path compression). Stale hints are never used, so the
        hints of ancestors need no update when a subtree grows.
        """
        w, k = p, 0
        while w.kids and k < _BUDGET:
            w = w.kids[-1]
            k += 1
        if not w.kids:
            return w
        if self._is_last(p, p.last):
            return p.last
        path, w = [p], p
        while w.kids:
            w = w.kids[-1]
            if self._is_last(w, w.last):
                w = w.last
                break
            path.append(w)
        for v in path:
            v.last = w
        return w

    @staticmethod
    def _subtree_first_last_q2(p: DNode) -> DNode:
        """Last node of p's subtree in Q2 (siblings reversed): follow first children."""
        w = p
        while w.kids:
            w = w.kids[0]
        return w

    def next_in_q1(self, node) -> Optional[str]:
        """The node after ``node`` in Q1, as a name, or None after the last node. Q1 is the
        display order of a tree view (parents before children, siblings in insertion order)."""
        c = self._node(node).c1.next
        return c.node.name if c is not None and c.node is not None else None

    def subtree_last(self, node):
        """Last node of the subtree of ``node`` in Q1, as a name (the subtree is the block from
        ``node`` to it). Usually O(1) when asked again for the same node."""
        return self._subtree_last_node(self._node(node)).name

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
        if not p.kids:
            p.kids = None
        self._q1.remove(n.name)
        self._q2.remove(n.name)
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
        last1 = self._subtree_last_node(n)
        last2 = self._subtree_first_last_q2(n)
        removed = self._q1.cut_block(n.name, last1.name)
        self._q2.cut_block(n.name, last2.name)
        p = n.up
        p.kids.remove(n)
        if not p.kids:
            p.kids = None
        for v in removed:
            self._forget(self._nodes[v])
        self._reshapes += 1
        return removed

    def cut_n_paste(self, subtree_root, new_parent) -> None:
        """Detach the subtree rooted at ``subtree_root`` and attach it under ``new_parent``.

        The subtree keeps its internal shape and becomes the last child of
        ``new_parent``. ``new_parent`` must not lie inside the moved subtree,
        and the root cannot be moved.
        """
        u = self._node(subtree_root)
        p = self._node(new_parent)
        if u is self._root:
            raise ValueError("the root cannot be moved")
        if p is u or self._in(u, p):
            raise ValueError("new_parent lies inside the subtree being moved")
        last1 = self._subtree_last_node(u)
        last2 = self._subtree_first_last_q2(u)
        block1 = self._q1.cut_block(u.name, last1.name)
        block2 = self._q2.cut_block(u.name, last2.name)
        moved = [self._nodes[v] for v in block1]
        for v in moved:
            v.owner = None                 # detached for a moment: their hints and cells are not valid
        old = u.up
        old.kids.remove(u)
        if not old.kids:
            old.kids = None
        # Same placement rule as insert: Q2 right after the parent,
        # Q1 right after the current last node of the parent's subtree.
        last = self._subtree_last_node(p)
        self._q2.paste_block_after(block2, p.name)
        self._q1.paste_block_after(block1, last.name)
        for v in moved:                    # the pasted cells are new objects
            v.owner = self
            v.c1, v.c2 = self._q1._cells[v.name], self._q2._cells[v.name]
            v.c1.node = v.c2.node = v
        u.up = p
        if p.kids is None:
            p.kids = [u]
        else:
            p.kids.append(u)
        p.last = last1
        self._reshapes += 1

    def _forget(self, n: DNode) -> None:
        del self._nodes[n.name]
        n.owner = None
        n.up = n.kids = n.last = None

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

    def _name(self, x) -> str:
        return x.name if x.__class__ is DNode else x

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
    def Q1(self) -> DList:
        """The Q1 projection itself, for list-level checks (is_left_of, index, ...).

        Live view: read it, but change the tree only through DTree methods.
        """
        return self._q1

    @property
    def Q2(self) -> DList:
        """The Q2 projection itself, for list-level checks. Live view, as Q1."""
        return self._q2

    @property
    def q1(self) -> List[str]:
        """Q1 as a plain list of node names (a copy, without the markers)."""
        return self._q1.to_list()

    @property
    def q2(self) -> List[str]:
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
        return f"DTree({self.tree_id!r}, size={self.size})\n  {self._q1!r}\n  {self._q2!r}"

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
        return [k.name for k in (self._node(node).kids or ())]

    def can_reach(self, u, v) -> bool:
        """True if there is a directed path of length >= 1 from u to v (names or handles).

        Irreflexive: can_reach(u, u) is False. With handles: two position comparisons.
        """
        if u.__class__ is DNode:
            if u.owner is not self:
                return False
        else:
            u = self._nodes.get(u)
            if u is None:
                return False
        if v.__class__ is DNode:
            if v.owner is not self:
                return False
        else:
            v = self._nodes.get(v)
            if v is None:
                return False
        a, b = u.c1, v.c1
        if not a.num * b.den < b.num * a.den:
            return False
        a, b = u.c2, v.c2
        return a.num * b.den < b.num * a.den

    def can_not_reach(self, u, v) -> bool:
        return not self.can_reach(u, v)

    def is_root(self, node) -> bool:
        return self.contains(node) and self._node(node) is self._root

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
        out, c = [n.name], n.c1.next
        end = self._subtree_last_node(n).c1
        if end is n.c1:
            return out
        while True:
            out.append(c.name)
            if c is end:
                return out
            c = c.next

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
        if a is not b and not self.can_reach(a, b):
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

    # -- helpers ----------------------------------------------------------
    # -- and/or queries on the topology -----------------------------------
    def vmin(self, nodes: Iterable[str] = ()) -> "VMin":
        """Constructed node VMin: the minimum of each index over the nodes (see VMin)."""
        return VMin(self, nodes)

    def vmax(self, nodes: Iterable[str] = ()) -> "VMax":
        """Constructed node VMax: the maximum of each index over the nodes (see VMax)."""
        return VMax(self, nodes)

    def umin(self, nodes: Iterable[str] = ()) -> "UMin":
        """Constructed node UMin: the minimum of each index over the nodes (see UMin)."""
        return UMin(self, nodes)

    def umax(self, nodes: Iterable[str] = ()) -> "UMax":
        """Constructed node UMax: the maximum of each index over the nodes (see UMax)."""
        return UMax(self, nodes)

    def _require(self, node) -> None:
        self._node(node)


class _VNode:
    """A constructed node for a set S of tree nodes (E. Olgac, "Topology and Structure of
    Directed Graphs - Inducing a Subgraph", 2021): the minimum (VMin, UMin) or maximum
    (VMax, UMax) of each index over S. V means S takes the target role, can_reach(u, S),
    and U the source role, can_reach(S, v); UMin and VMin hold the same numbers.

    It stores no positions, only the members and, for each of Q1 and Q2, the member holding
    the minimal (or maximal) index there; the two may be different nodes, so the constructed
    node usually corresponds to no real node. Insertions and renumbering keep the order of
    existing nodes, so it stays valid while the tree grows. After a deletion or a cut_n_paste it is
    recomputed from the remaining members on its next use. Members are added with ``add`` and
    removed with ``discard``.
    """

    _lowest = True  # VMin keeps the leftmost member, VMax the rightmost

    def __init__(self, tree: "DTree", nodes: Iterable[str] = ()) -> None:
        self._t = tree
        self._members: List[str] = []    # in Q1 order
        self._seen: set = set()
        self._c1: Optional[str] = None
        self._c2: Optional[str] = None
        self._reshapes = tree._reshapes
        for v in nodes:
            self.add(v)

    def _better(self, q: DList, v: str, c: Optional[str]) -> bool:
        if c is None:
            return True
        return q.precedes(v, c) if self._lowest else q.precedes(c, v)

    def add(self, node: str) -> "_VNode":
        """Add a node of the tree (name or handle) to the set; returns the constructed node itself."""
        node = self._t._name(node)
        self._t._require(node)
        if node in self._seen:
            return self
        self._check()
        self._seen.add(node)
        q1 = self._t._q1
        lo, hi = 0, len(self._members)       # keep members sorted by Q1 order
        while lo < hi:
            mid = (lo + hi) // 2
            if q1.precedes(node, self._members[mid]):
                hi = mid
            else:
                lo = mid + 1
        self._members.insert(lo, node)
        if self._better(self._t._q1, node, self._c1):
            self._c1 = node
        if self._better(self._t._q2, node, self._c2):
            self._c2 = node
        self._added(node)
        return self

    def discard(self, node) -> "_VNode":
        """Remove a node (name or handle) from the set; no error if it is not a member.

        O(log k) to find it plus the list removal; if it held an index (the minimal or
        maximal position in Q1 or Q2), the index nodes are recomputed in O(k). Returns the
        constructed node itself. Typical use: expanding a node in a tree view, after it was
        added to the set of collapsed nodes.
        """
        node = self._t._name(node)
        self._check()
        if node not in self._seen:
            return self
        self._seen.discard(node)
        q1, m = self._t._q1, self._members
        lo, hi = 0, len(m)                  # members are sorted by Q1 order
        while lo < hi:
            mid = (lo + hi) // 2
            if q1.precedes(m[mid], node):
                lo = mid + 1
            else:
                hi = mid
        del m[lo]
        if node == self._c1 or node == self._c2:
            t = self._t
            self._c1 = self._c2 = None
            for v in self._members:
                if self._better(t._q1, v, self._c1):
                    self._c1 = v
                if self._better(t._q2, v, self._c2):
                    self._c2 = v
        self._discarded(node)
        return self

    def __contains__(self, node) -> bool:
        self._check()
        return self._t._name(node) in self._seen

    def _added(self, node: str) -> None:
        """Hook for subclasses that keep more than the index nodes."""

    def _discarded(self, node: str) -> None:
        """Hook for subclasses that keep more than the index nodes."""

    def _rebuilt(self) -> None:
        """Hook for subclasses that keep more than the index nodes."""

    def refresh(self) -> None:
        """Drop deleted members and recompute the index nodes."""
        t = self._t
        q1 = t._q1
        self._members = sorted((v for v in self._members if t.contains(v)),
                               key=lambda v: q1.index(v))
        self._seen = set(self._members)
        self._c1 = self._c2 = None
        for v in self._members:
            if self._better(t._q1, v, self._c1):
                self._c1 = v
            if self._better(t._q2, v, self._c2):
                self._c2 = v
        self._reshapes = t._reshapes
        self._rebuilt()

    def _check(self) -> None:
        t = self._t
        if self._reshapes != t._reshapes:
            self.refresh()

    @property
    def members(self) -> List[str]:
        self._check()
        return list(self._members)

    @property
    def index_nodes(self) -> tuple:
        """The members holding the minimal (VMin, UMin) or maximal (VMax, UMax) index in Q1 and in Q2 (possibly two different nodes)."""
        self._check()
        return self._c1, self._c2

    def __len__(self) -> int:
        self._check()
        return len(self._members)


class VMin(_VNode):
    """S in the target role, can_reach(u, S). Minimum of each index over a node set: u reaches all of the set exactly when u lies
    strictly left of VMin in both Q1 and Q2."""

    _lowest = True

    def reaches_all(self, u) -> bool:
        """True if u reaches every node of the set (vacuously True for an empty set)."""
        u = self._t._name(u)
        self._check()
        t = self._t
        if not t.contains(u):
            return False
        if self._c1 is None:
            return True
        return t._q1.precedes(u, self._c1) and t._q2.precedes(u, self._c2)


class VMax(_VNode):
    """S in the target role, can_reach(u, S). Maximum of each index over a node set: lying
    strictly left of VMax in both Q1 and Q2 is necessary for u to reach some of the set, but
    not sufficient, so may_reach_some is only a filter; reaches_some is exact."""

    _lowest = False

    def may_reach_some(self, u) -> bool:
        """Fast rejection: False means u reaches no node of the set. True is not a confirmation."""
        u = self._t._name(u)
        self._check()
        t = self._t
        if self._c1 is None or not t.contains(u):
            return False
        return t._q1.precedes(u, self._c1) and t._q2.precedes(u, self._c2)

    def reaches_some(self, u) -> bool:
        """True if u reaches at least one node of the set (exact).

        The subtree of u is the block directly after u in Q1, so u reaches some member
        exactly when the first member after u in Q1 lies in it: a binary search over the
        members (kept in Q1 order) and one reachability test.
        """
        u = self._t._name(u)
        if not self.may_reach_some(u):
            return False
        t, m = self._t, self._members
        q1 = t._q1
        lo, hi = 0, len(m)
        while lo < hi:
            mid = (lo + hi) // 2
            if q1.precedes(u, m[mid]):
                hi = mid
            else:
                lo = mid + 1
        return lo < len(m) and t.can_reach(u, m[lo])


class UMax(_VNode):
    """S in the source role, can_reach(S, v). Maximum of each index over a node set: v is
    reached by all of the set exactly when v lies strictly right of UMax in both Q1 and Q2."""

    _lowest = False

    def reached_by_all(self, v) -> bool:
        """True if every node of the set reaches v (vacuously True for an empty set)."""
        v = self._t._name(v)
        self._check()
        t = self._t
        if not t.contains(v):
            return False
        if self._c1 is None:
            return True
        return t._q1.precedes(self._c1, v) and t._q2.precedes(self._c2, v)


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

    def __init__(self, tree: "DTree", nodes: Iterable[str] = ()) -> None:
        self._tops: List[str] = []       # topmost members, in Q1 order
        super().__init__(tree, nodes)

    def _last_top_before(self, v: str) -> int:
        """Number of topmost members strictly left of v in Q1."""
        q1, m = self._t._q1, self._tops
        lo, hi = 0, len(m)
        while lo < hi:
            mid = (lo + hi) // 2
            if q1.precedes(m[mid], v):
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _covered(self, v: str) -> bool:
        i = self._last_top_before(v)
        return i > 0 and self._t.can_reach(self._tops[i - 1], v)

    def _added(self, node: str) -> None:
        if self._covered(node):
            return                       # an ancestor of node is already in the set
        i = self._last_top_before(node)
        t, m = self._t, self._tops
        while i < len(m) and t.can_reach(node, m[i]):
            del m[i]                     # node is above them: they are no longer topmost
        m.insert(i, node)

    def _discarded(self, node: str) -> None:
        if node in self._tops:           # members it covered may become topmost
            self._rebuilt()

    def _rebuilt(self) -> None:
        self._tops = []
        t = self._t
        for v in self._members:          # Q1 order: ancestors come first
            if not (self._tops and t.can_reach(self._tops[-1], v)):
                self._tops.append(v)

    def may_be_reached_by_some(self, v) -> bool:
        """Fast rejection: False means no node of the set reaches v; True is not a confirmation."""
        v = self._t._name(v)
        self._check()
        t = self._t
        if self._c1 is None or not t.contains(v):
            return False
        return t._q1.precedes(self._c1, v) and t._q2.precedes(self._c2, v)

    def reached_by_some(self, v) -> bool:
        """True if at least one node of the set reaches v (exact, O(log k))."""
        v = self._t._name(v)
        if not self.may_be_reached_by_some(v):
            return False
        return self._covered(v)

    def covering(self, v) -> Optional[str]:
        """The topmost member of the set that reaches v, or None if no member does (O(log k)).

        With the collapsed nodes of a tree view as a UMin, this is the visible row that
        contains v: None means v itself is visible.
        """
        v = self._t._name(v)
        self._check()
        if not self._t.contains(v):
            return None
        i = self._last_top_before(v)
        if i > 0 and self._t.can_reach(self._tops[i - 1], v):
            return self._tops[i - 1]
        return None
