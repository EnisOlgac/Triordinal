# DTree for Python (triordinal-dtree)

Python implementation of `DTree`, the incremental encoding of the topology of directed trees by two projections Q1 and Q2 (see the [API reference](https://github.com/EnisOlgac/Triordinal/blob/main/docs/API.md) and the [paper](https://doi.org/10.5772/intechopen.1013408)). No dependencies; Python 3.8+.

```
pip install triordinal-dtree
```

The package is imported as `triordinal.dtree` (`from triordinal.dtree import DTree`). It continues `dtree-encoding` (imported as `dtree`), whose last versions point here. It depends only on `triordinal-dlist`, the shared list with rational positions.

```python
from triordinal.dtree import DTree

t = DTree("P1")
t.insert("A", "B")
t.insert("B", "C")

t.can_reach("A", "C")    # True
t.path_to_root("C")      # ['C', 'B', 'A']
t.q1, t.q2               # (['A', 'B', 'C'], ['A', 'B', 'C'])

t.insert("A", "D")
t.cut_n_paste("C", "D")  # move subtree C under D
t.delete("B")            # B's children (none left) move up to A
t.delete_subtree("D")    # removes D and C
```

Load one of the example files (`parent: child1; child2` per line):

```python
t = DTree.from_file("Test.csx")   # e.g. examples/Test.csx from the repository
```

## API (C# name → Python name)

| C# (docs) | Python |
|---|---|
| `DTree(id)` | `DTree(tree_id="P1")` |
| `Insert(parent, child)` | `insert(parent, child)` (last child) |
| `InsertAfter`, `InsertBefore` | `insert_after(sibling, child)`, `insert_before(sibling, child)` |
| `AddLine` | `add_line(line)` (`p: c`, `s > c`, `s < c`; also in `from_file`) |
| `Contains(node)` | `contains(node)` / `node in t` |
| `GetParent(node)` | `get_parent(node)` (`None` for the root) |
| `CutNPaste(u, p)` | `cut_n_paste(subtree_root, new_parent)` |
| `Delete(node)` | `delete(node)`—children move up to the parent |
| — | `delete_subtree(node)`—removes the node and all descendants |
| `Q1`, `Q2` | `Q1`, `Q2` (the `DList` projections, for list-level checks); `q1`, `q2` (plain lists, without the `[` `]` markers) |
| `Source`, `Sink` | `source`, `sink` |
| `CanReach`, `CanNotReach` | `can_reach`, `can_not_reach` |
| `IsRoot`, `IsLeaf` | `is_root`, `is_leaf` |
| `IsAncestor`, `IsDescendant` | `is_ancestor`, `is_descendant` |
| `SameSubtree`, `SubtreeSize` | `same_subtree`, `subtree_size` (plus `subtree`) |
| `Depth` | `depth` (root = 0) |
| `PathToRoot`, `RootToPath` | `path_to_root`, `root_to_path` (plus `path(u, v)`) |
| `GetNode`, `TryGetNode`, `DNode` | `get_node`, `try_get_node`, `DNode` (node handles; `insert` returns one) |
| `SubtreeLast` | `subtree_last` (last node of a subtree in Q1) |
| `NextInQ1` | `next_in_q1` (next node in Q1, the display order; `None` at the end) |
| `VMin`, `VMax`, `UMin`, `UMax` (of nodes) | `vmin`, `vmax`, `umin`, `umax` |
| `ReachesAll`, `MayReachSome`, `ReachesSome` | `reaches_all`, `may_reach_some`, `reaches_some` |
| `ReachedByAll`, `MayBeReachedBySome`, `ReachedBySome` | `reached_by_all`, `may_be_reached_by_some`, `reached_by_some` |
| `Add`, `Discard`, `Contains` (of a constructed node) | `add`, `discard`, `node in s` |
| `UMin.Covering` | `covering` (topmost member that reaches a node; `None` if none) |

## Semantics

- Every method accepts a node name or a node handle (`DNode`). `insert` returns the handle of the new node, `get_node(name)` gives the handle of an existing one. A handle refers directly to the node's positions in Q1 and Q2, so `can_reach` on handles is two position comparisons without any lookup by name. Handles of deleted nodes, or of another tree, are rejected (KeyError) or reported as unreachable.

- `can_reach(u, v)` is irreflexive: no node reaches itself, so `can_reach(u, u)` is `False`. (The C# prototype is reflexive.)
- `is_ancestor(u, v)` equals `can_reach(u, v)` and is likewise proper.
- `delete(v)` re-attaches v's children to v's parent, in v's place among its siblings.
- `delete_subtree(v)` removes v with all its descendants and returns them in Q1 order.
- `cut_n_paste(u, p)` moves the subtree rooted at u under p as p's last child; p must not lie inside u's subtree.
- And/or queries on the topology: the constructed nodes `vmin(S)`, `vmax(S)` (S as target) and `umin(S)`, `umax(S)` (S as source) take the minimum or maximum of each index over S, separately in Q1 and Q2. `reaches_all` and `reached_by_all` are exact O(1) tests; `may_reach_some` and `may_be_reached_by_some` are only filters, and `reaches_some` and `reached_by_some` are exact in O(log k). Members are added with `add` and removed with `discard`. A constructed node stays valid under insertions and is recomputed automatically after `delete`, `delete_subtree` or `cut_n_paste`. See [and/or queries on the topology](https://github.com/EnisOlgac/Triordinal/blob/main/docs/and-or-queries.md).
- Projection positions are fractions: a new node gets the mediant (a+c)/(b+d) of its neighbors, so normally no other node moves. Only rare alternating insertion patterns trigger a local renumbering. Tree depth and width are unbounded. `t.Q1.index(v)` returns a position as a `Fraction`.

## Tests

```
python -m unittest discover -s tests
```

Every operation is checked against a brute-force parent/children model on random trees, including random sequences of deletes and moves.

## Benchmarks

The benchmarks come with the package, so you can measure on your own machine:

```
python -m triordinal.dtree.bench            # trees of 10,000 and 100,000 nodes
python -m triordinal.dtree.bench --quick    # a few seconds
python -m triordinal.dtree.bench --dynamic  # only the dynamic updates and the tree view
python -m triordinal.dtree.bench --note "idle machine"   # remark for the report
python -m triordinal.dtree.bench 1000000    # custom sizes
```

In a clone of the repository, `python python/benchmarks/bench.py` runs the same code from the sources.

The script prints Markdown tables: build time and renumbering counts per tree shape (random, chain, star at the root, star at an inner node, alternating worst case), list growth at either end, and timings for `can_reach`, `depth`, `delete`, `cut_n_paste` and `delete_subtree`, and comparisons with a classical parent walk: reachability by tree depth, and/or queries with constructed nodes, dynamic updates (insertions with 1 or 10 queries each, and static pre/post numbers at depths 100 and 1,000), and a tree view with expand/collapse. Each dynamic measurement is the best of three runs. Each `DList` keeps the counters `renumber_count` and `renumber_moved`, so the same figures are available in your own code via `t.Q1` and `t.Q2`.

Every run also writes its tables as a Markdown report to `benchmarks/python/`—in the current directory, or at the repository root when run inside a clone— named after date and time (for example `2026-10-17_14-18.md`), with a header giving the DTree and Python versions, the operating system and the processor; `--no-save` skips it. The C# benchmarks (`dotnet run --project csharp/Triordinal.Tests -c Release -- bench`) write theirs to `benchmarks/csharp/`.

## Provenance

Design and API: Enis Olgac. This Python port was written with Claude (Anthropic) from the C# original and the API reference.
