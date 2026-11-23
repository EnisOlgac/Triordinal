# DTree for Python (triordinal-dtree)

Python implementation of `DTree`, the incremental encoding of the topology of directed trees. Since 3.0.0 a DTree keeps one projection, Q1 (the pre-order), and the structure of the tree in its vertices; reachability is decided by comparing positions in Q1. See the [repository](https://github.com/EnisOlgac/Triordinal), the [API reference](https://github.com/EnisOlgac/Triordinal/blob/main/docs/API.md) and the [paper](https://doi.org/10.5772/intechopen.1013408). Python 3.10+. How one list and two lists differ, and the way to 3.0: [One list and two lists](https://github.com/EnisOlgac/Triordinal/blob/main/docs/one-and-two-lists.md).

```
pip install triordinal-dtree
```

The package is imported as `triordinal.dtree` (`from triordinal.dtree import DTree`). It continues `dtree-encoding` (imported as `dtree`), whose last versions point here. It depends only on `triordinal-dlist`, the shared list with rational positions.

```python
from triordinal.dtree import DTree

t = DTree("P1")
t.insert("A", "B")       # the first insert makes A the root
t.insert("B", "C")
t.insert("A", "D")       # D becomes A's last kid

t.can_reach("A", "C")    # True
t.path_to_root("C")      # ['C', 'B', 'A']
t.q1                     # ['A', 'B', 'C', 'D']

t.cut_n_paste("C", "D")  # move subtree C under D
t.delete("B")            # B's kids (none left) move up to A
t.delete_subtree("D")    # removes D and C
```

Load one of the example files (`parent: child1; child2` per line; `sibling > child` and `sibling < child` insert after or before a sibling):

```python
t = DTree.from_file("Test.csx")   # e.g. examples/Test.csx from the repository
```

DTree 3.0 is not compatible with 2.x. The earlier encodings remain in the package for comparison, with their own API (as documented for 2.4.2): `from triordinal.dtree.two_lists import DTree` (DTree 2.x on Q1 and Q2) and `from triordinal.dtree.euler import EulerTree` (one list with closing cells).

## API (C# name → Python name)

| C# | Python |
|---|---|
| `DTree(id, positions)` | `DTree(tree_id="P1", positions="rational")` (positions: `"rational"` or `"integer"`) |
| `FromFile`, `AddLine` | `from_file(path, tree_id=None, positions="rational")`, `add_line(line)` |
| `Insert(parent, child)` | `insert(parent, child)`: last kid; the first call makes `parent` the root |
| `InsertFirst(parent, child)` | `insert_first(parent, child)`: first kid, directly after the parent in Q1 |
| `InsertBefore`, `InsertAfter` | `insert_before(sibling, child)`, `insert_after(sibling, child)` |
| `Delete(node)` | `delete(node)`: the kids take the node's place among its siblings |
| `DeleteSubtree(node)` | `delete_subtree(node)`: returns the removed names in Q1 order |
| `CutNPaste(u, p)` | `cut_n_paste(subtree_root, new_parent)`: as the new parent's last kid |
| `CanReach`, `CanNotReach` | `can_reach`, `can_not_reach` |
| `IsAncestor`, `IsDescendant` | `is_ancestor`, `is_descendant` |
| `GetParent`, `Children` | `get_parent` (`None` for the root), `children` |
| `IsRoot`, `IsLeaf`, `Depth` | `is_root`, `is_leaf`, `depth` (root = 0) |
| `PathToRoot`, `Subtree`, `SubtreeSize` | `path_to_root`, `subtree` (Q1 order), `subtree_size` |
| `Q1` | `q1` (a list of names, without the markers); iterating the tree gives the same order |
| `Contains`, `Count`, `Root` | `contains(node)` / `node in t`, `len(t)`, `root` |
| `GetNode`, `TryGetNode`, `DNode` | `get_node`, `try_get_node`, `DNode` (node handles; every insert returns one) |
| `DNode.Parent`, `DNode.Children`, `DNode.IsInTree` | `parent`, `children`, `is_in_tree` |
| `VMin`, `VMax`, `UMin`, `UMax` (of nodes) | `vmin`, `vmax`, `umin`, `umax` |
| `ReachesAll`, `ReachesSome` | `reaches_all`, `reaches_some` |
| `ReachedByAll`, `ReachedBySome`, `Covering` | `reached_by_all`, `reached_by_some`, `covering` |
| `RenumberCount` | `renumber_count` |

## Semantics

- Every method accepts a node name or a node handle (`DNode`). A name that is not in the tree raises `KeyError`, and so does a handle of a removed node or of another tree.
- `can_reach(u, v)` is irreflexive: no node reaches itself. `is_ancestor(u, v)` equals `can_reach(u, v)`.
- The block of *u* in Q1 runs from its own cell to just before its delimiter: its right sibling, or, when it is the last kid, its parent's delimiter. `can_reach` decides "v lies in u's block" as a cascade of local steps: *v* is not after *u*; *u* has no kids; *u* has a right sibling (or is the root); *u*'s last kid; only then is the delimiter looked for, up through the ancestors that are last kids.
- A sequence of only kids (a vertical run) is crossed in one step: its members share an object that knows its top. Where a vertex gets a second kid the run is cut, and where it is left with one kid two runs are joined; only the shorter part gets a new run object. A tree that is nothing but a sequence is a list; use `DList` for it.
- A new kid goes into Q1 directly after its parent (`insert_first`, or the first kid), directly before its right sibling (`insert_before`), or before its parent's delimiter (`insert`, `insert_after` a last kid).
- `delete(v)` re-attaches v's kids to v's parent, in v's place among its siblings. `delete_subtree(v)` removes v with all its descendants. `cut_n_paste(u, p)` moves the subtree of u under p as p's last kid; p must not lie inside u's subtree.
- And/or queries: a constructed node (`vmin(S)`, `vmax(S)` with S as the target, `umin(S)`, `umax(S)` with S as the source) is built for the query at hand. It sorts the members by their position in Q1 and, for `umin` and `umax`, finds their delimiters. `reaches_all` and `reached_by_all` are O(1), `reaches_some`, `reached_by_some` and `covering` O(log k). After the tree changes, build it again.
- Every operation checks its arguments before it changes anything: an operation that raises leaves the tree as it was. Node names are non-empty strings other than the markers `[` and `]`.
- Positions are fractions: a new node gets the mediant (a+c)/(b+d) of its neighbors, so normally no other node moves; a region is renumbered only when a new position can no longer be stored. `positions="integer"` gives integer positions instead: midpoints in [0, 2⁶²], faster to compare and renumbered more often. Tree depth and width are unbounded.

## Tests

```
python -m unittest discover -s tests
```

`tests/test_dtree.py` checks every operation of DTree 3.0 against a brute-force parent/kids model on random trees, with deletes and moves, both kinds of position and deep trees, including every vertical run and all four constructed nodes; every example file gives the same Q1 and the same reachability as DTree 2.x. The other test files cover DTree 2.x and EulerTree.

## Benchmarks

The benchmarks come with the package, so you can measure on your own machine:

```
python -m triordinal.dtree.bench3           # DTree 3.0 against DTree 2.x and EulerTree
python -m triordinal.dtree.bench3 --quick   # a few seconds
python -m triordinal.dtree.bench            # the benchmarks of DTree 2.x and EulerTree (see 2.4.2)
```

`bench3` prints Markdown tables: building and querying random, chain, star and reading-order trees; how often each step of the query cascade decides; the review pattern (a chain grown at the bottom, a child near the top); kids appended under the middle of a chain; random moves; and memory per node. Each timing is the best of three runs, after `gc.collect()`.

## Provenance

Design and API: Enis Olgac. This Python implementation was written with Claude (Anthropic); DTree 3.0's structure was designed by Enis Olgac and implemented with Claude.
