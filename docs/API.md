# DTree Public API Reference (3.0)

C# names, with the Python names where they differ (Python: `snake_case`, the same arguments). DTree 2.x on two projections (`DirectedTrees.TwoLists.DTree`, Python `triordinal.dtree.two_lists.DTree`) and EulerTree keep the API they had in 2.4.2; for them see the [2.4.2 version of this page](https://github.com/EnisOlgac/Triordinal/blob/v2.4.2/docs/API.md).

## Overview

`DTree` represents a single-rooted directed tree whose vertices are identified by unique strings. It keeps one projection, Q1, the pre-order with kids left to right, and the structure of the tree in its vertices: each vertex knows its parent, its kids list (read left to right from one end, right to left from the other), its handle in its parent's kids list, and its cell in Q1. Positions in Q1 are rational (the default) or integer.

The block of a vertex *u* in Q1 runs from its own cell to just before its *delimiter*: its right sibling, or, when *u* is the last kid, its parent's delimiter (SINK above the root). *u* reaches *v* exactly when *v* lies after *u* and before *u*'s delimiter. A sequence of only kids (a *vertical run*) shares one run object that knows its top, so looking for a delimiter crosses it in one step.

Every operation accepts names or node handles (`DNode`). Every operation checks its arguments before it changes anything, so an operation that throws leaves the tree as it was. Node names are non-empty strings other than the markers `[` and `]`.

| situation | C# | Python |
|---|---|---|
| a name that is not in the tree | `KeyNotFoundException` | `KeyError` |
| a handle of a removed node or of another tree | `ArgumentException` | `KeyError` |
| a name that is null / not a string | `ArgumentNullException` | `TypeError` |
| an empty name, a marker, a name already in the tree | `ArgumentException` | `ValueError` |
| deleting or moving the root, a sibling of the root, a move into the moved subtree | `InvalidOperationException` | `ValueError` |

## Constructor

### `DTree(string treeId = "P1", Positions positions = Positions.Rational)`
Python: `DTree(tree_id="P1", positions="rational")`.
- The root is the parent of the first inserted edge.
- `positions`: `Positions.Rational` (mediants, the default) or `Positions.Integer` (midpoints in [0, 2⁶²]). Integer positions are faster to compare; rational positions are renumbered far less often.

### `static DTree FromFile(string path, string? treeId = null, Positions positions = Positions.Rational)`
Read the `.csx` description format, one line at a time with `AddLine`. Empty lines and lines starting with `#`, `--` or `**` are skipped; `@@` ends the description. The tree id defaults to the file name.

### `List<DNode> AddLine(string line)`
Apply one line and return the new handles:
- `parent: c1; c2` appends the children as last kids of `parent`;
- `sibling > c1; c2` inserts them directly after `sibling`, in that order;
- `sibling < c1; c2` inserts them directly before `sibling`.

A line without `:`, `>` or `<` throws `ArgumentException` (Python `ValueError`).

## Insertion

All insertions return the new vertex's handle. The child must not be in the tree yet.

### `DNode Insert(string parent, string child)` / `Insert(DNode parent, string child)`
Append `child` as the **last** kid of `parent`. The first call makes `parent` the root. In Q1 the child goes before its parent's delimiter: directly after the parent if it has no kids yet, otherwise after the parent's block.

### `DNode InsertFirst(string parent, string child)` / `InsertFirst(DNode parent, string child)`
Python: `insert_first`. Insert `child` as the **first** kid of `parent`: directly after the parent in Q1, without looking for any delimiter. The first call makes `parent` the root.

### `DNode InsertBefore(string sibling, string child)` / `InsertAfter(string sibling, string child)`
Python: `insert_before`, `insert_after`. Insert `child` under the same parent, directly before `sibling` (in Q1 directly before the sibling's cell) or directly after it (after the sibling's block). The root has no siblings.

## Changes

### `void Delete(string node)`
Remove `node`; its kids take its place among its siblings, in order. The root cannot be deleted.

### `List<string> DeleteSubtree(string node)`
Python: `delete_subtree`. Remove `node` and all its descendants; returns their names in Q1 order.

### `void CutNPaste(string subtreeRoot, string newParent)`
Python: `cut_n_paste`. Move the subtree of `subtreeRoot` under `newParent`, as its last kid. Its block is cut from Q1 and pasted at the new place as one piece. `newParent` must not lie inside the moved subtree; the root cannot be moved.

## Reachability

### `bool CanReach(string u, string v)` / `CanReach(DNode u, DNode v)`
Python: `can_reach`. *u* reaches *v*: *u* is a proper ancestor of *v*. Irreflexive. Decided as a cascade of local steps:
1. *v* is not right of *u* in Q1: false;
2. *u* has no kids: false;
3. *u* has a right sibling (or is the root): *v* must lie before it;
4. *u*'s last kid: *v* up to it is reached; if the last kid is a leaf, its next cell in Q1 is *u*'s delimiter;
5. otherwise the delimiter is looked for, up through the ancestors that are last kids; a vertical run is crossed in one step.

### `bool CanNotReach(string u, string v)`
Python: `can_not_reach`. The negation of `CanReach`.

### `bool IsAncestor(string u, string v)` / `bool IsDescendant(string u, string v)`
Python: `is_ancestor`, `is_descendant`. `IsAncestor(u, v)` equals `CanReach(u, v)`; `IsDescendant(u, v)` equals `CanReach(v, u)`.

## Structure

| C# | Python | |
|---|---|---|
| `string? GetParent(string node)` | `get_parent` | the parent's name; null (`None`) for the root |
| `List<string> Children(string node)` | `children` | the kids, left to right |
| `bool IsRoot(string node)`, `bool IsLeaf(string node)` | `is_root`, `is_leaf` | |
| `int Depth(string node)` | `depth` | root = 0 |
| `List<string> PathToRoot(string node)` | `path_to_root` | from the node up to the root |
| `List<string> Subtree(string node)` | `subtree` | the node and its descendants, in Q1 order |
| `int SubtreeSize(string node)` | `subtree_size` | |
| `List<string> Q1` | `q1` | all vertices in Q1 order, without the markers |
| `string? Root`, `int Count` | `root`, `len(t)` | |
| `bool Contains(string node)` | `contains`, `node in t` | never throws |
| `DNode GetNode(string name)`, `bool TryGetNode(string name, out DNode node)` | `get_node`, `try_get_node` | handles |
| `Positions Positions`, `long RenumberCount` | `positions`, `renumber_count` | |

### `DNode`
A vertex's handle, valid while the vertex is in its tree: `Name`, `Parent` (null for the root), `Children` (left to right), `IsInTree`. Python: `name`, `parent`, `children`, `is_in_tree`.

## And/or Queries on the Topology

A *constructed node* reduces a set *S* of vertices to what an and/or query needs, an idea of the author (2021). Its name says which role *S* plays in `CanReach(u, v)`: *V* when *S* is the target, *U* when *S* is the source. In DTree 3.0 it is built for the query at hand: it sorts the members by their position in Q1 and, for `UMax` and `UMin`, finds their delimiters, O(k log k) in all. After the tree changes, build it again. An empty set throws `ArgumentException` (Python `ValueError`).

### `VMin VMin(IEnumerable<string> nodes)`, `VMax VMax(…)`, `UMin UMin(…)`, `UMax UMax(…)`
Also with `IEnumerable<DNode>`. Python: `vmin`, `vmax`, `umin`, `umax`.

### `bool VMin.ReachesAll(string u)`
*u* reaches every member: *u* lies before the first member and *u*'s delimiter after the last. O(1) plus *u*'s delimiter.

### `bool VMax.ReachesSome(string u)`
*u* reaches at least one member: the first member after *u* lies before *u*'s delimiter. O(log k).

### `bool UMax.ReachedByAll(string v)`
Every member reaches *v*: *v* lies after the last member and before the first of the members' delimiters. O(1).

### `bool UMin.ReachedBySome(string v)`, `string? UMin.Covering(string v)`
Some member reaches *v*. Only the topmost members count (those with no ancestor in *S*); their blocks are disjoint, so the last one before *v* decides. `Covering` returns that member, or null (`None`). O(log k).

### `List<string> Members`, `int Count`, `bool Contains(string node)`
The members in Q1 order, their number, membership. Python: `members`, `len(s)`, `node in s`.

## Counters (for the benchmarks)

`ClimbSteps` (Python `climb_steps`): steps taken looking for delimiters. `RunSteps` (`run_steps`): vertices given a new run object by cuts and joins of vertical runs.
