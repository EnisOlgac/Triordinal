# DTree Public API Reference

*Markdown edition of [`User.Doc.pdf`](User.Doc.pdf).*

## Overview

The `DTree` class represents a symbolic directed tree with a unique root and internal support for dual projections (Q1 and Q2). Each node is identified by a unique string. Edges are added incrementally, and projections are updated automatically. Structural operations preserve the tree's topological validity.

## Constructor

### `DTree(string id, bool strict = false, Positions positions = Positions.Rational)`
Create a new tree with a given identifier.
- Initializes a new directed tree with the given identifier.
- The root is determined implicitly as the source of the first inserted edge.
- Q1 and Q2 projections are initialized automatically.
- `strict`: queries about nodes (`CanReach`, `CanNotReach`, `IsAncestor`, `IsDescendant`, `IsRoot` and the queries of constructed nodes) throw for a name that is not in the tree (`KeyNotFoundException`) or a handle of a removed node (`ArgumentException`) instead of answering `false`. `Contains` and `SameSubtree` are membership tests and never throw. Python: `DTree(tree_id="P1", strict=False)`, raising `KeyError` in both cases.

- `positions`: the kind of position in Q1 and Q2, `Positions.Rational` (mediants, the default) or `Positions.Integer` (midpoints in [0, 2⁶²], as in classical order maintenance). Integer positions are faster to compare; rational positions are renumbered far less often (see [prior-art.md](prior-art.md)). Python: `positions="rational"` or `"integer"`.

Every operation checks its arguments before it changes anything, so an operation that throws leaves the tree as it was. Node names are non-empty strings other than the markers `[` and `]`.

### `EulerTree(string id = "E1", bool strict = false, Positions positions = Positions.Rational)`
The tree on one list: DTree's Q1 with its closing cells, the classical Euler-tour encoding. Namespace `Triordinal.DTree.Euler` (package `Triordinal.DTree`); Python: `from triordinal.dtree.euler import EulerTree`.
- The subtree of *u* is the block from *u* to its closing cell (*u* alone for a leaf); *u* reaches *v* exactly when *v* lies strictly inside *u*'s block. Two comparisons, as in DTree.
- Every method of DTree below is available, with the same meaning; the constructed nodes use the end of each member's block in place of its Q2 position.
- `Q2` does not exist (C#: `NotSupportedException`; Python: `AttributeError` for `Q2` and `q2`).
- `EulerTree.FromFile(path, treeId, strict, positions)` reads a description file into an EulerTree.

## Core Methods

### `void Insert(string parent, string child)`
Insert a new edge into the tree.
- Adds a directed edge from `parent` to `child`.
- The `parent` must already exist in the tree.
- The `child` must not already exist.
- Updates Q1 and Q2 projections accordingly.
- The new node becomes the **last** child of `parent`: in Q1 directly before the closing cell of `parent`, in Q2 directly after `parent`. O(1).

### `DNode InsertAfter(string sibling, string child)` / `DNode InsertBefore(string sibling, string child)`
Insert a new node as a sibling of an existing one, with the same parent.
- `InsertAfter`: `child` goes directly after `sibling` among the parent's children. In Q1 it is placed after the end of the sibling's subtree, in Q2 directly before the sibling.
- `InsertBefore`: `child` goes directly before `sibling`. In Q1 it is placed directly before the sibling, in Q2 after the end of the sibling's subtree there.
- Two local list insertions, as with `Insert`; no other node moves, and constructed nodes stay valid.
- The root has no siblings (`InvalidOperationException`; Python: `ValueError`). Both accept a name or a `DNode` handle and return the new handle.
- Python: `insert_after(sibling, child)`, `insert_before(sibling, child)`.

### `List<DNode> AddLine(string line)`
Apply one line of the description format used by the `.csx` files and `FromFile`:
- `p: c1; c2`: `c1` and `c2` become last children of `p`.
- `s > c1; c2`: `c1` goes directly after `s`, then `c2` directly after `c1`.
- `s < c1; c2`: `c1` and `c2` go directly before `s`, in that order.
- The children are added one by one; if one is rejected, those before it remain.
- Python: `add_line(line)`.

### `static DTree FromFile(string path, string? treeId = null, bool strict = false)`
Read a description file line by line with `AddLine`. Empty lines and lines starting with `#`, `--` or `**` are skipped, `@@` ends the description; any other line without `:`, `>` or `<` throws `ArgumentException` (Python: `ValueError`). Python: `DTree.from_file(path, tree_id=None, strict=False)`.

### `bool Contains(string node)`
Check if a node exists.
- Returns `true` if the specified node is present in the tree.
- Otherwise returns `false`.

### `string GetParent(string node)`
Return the parent of a node.
- Returns the parent of `node`.
- If `node` is the root, returns `null`.
- Throws an error if the node is not found.

## Structural Reconfiguration

### `void CutNPaste(string u1, string u2)`
Detach a subtree from its root and attach it to another.
- Extracts the subtree rooted at `u2` from the tree rooted at `u1`.
- The subtree is detached from its original parent and reattached under a new one.
- Ensures that no orphaned structure remains in the source tree.
- Both source and destination trees must be structurally valid after the operation.

### `void Delete(string node)`
Remove a node and reattach its children, if any, to its parent.
- Deletes `node` from the tree.
- If `node` has children, they are reattached to `RootOf(node)`.
- Behaves as a shorthand for `CutNPaste(node, RootOf(node))`.
- If `node` is the root, the operation is disallowed.

## Accessors

### `Projection Q1`
Return the Q1 projection.
- A read-only, live view of Q1 (left-to-right traversal): the nodes in list order, with the list-level checks `IsLeftOf`, `IsRightOf`, `Precedes`, `Index`, `IndexValue`, `Next`, `Prev`, `Contains`, `IsSameAs`, `ToList`, `Count`, `RenumberCount`, `RenumberMoved`. It has no methods that change the list; the tree changes only through `DTree` methods.
- Closing cells are not shown: `Next` and `Prev` pass over them.
- Python: `t.Q1`; `t.q1` is a plain list of names.

### `Projection Q2`
Return the Q2 projection.
- A read-only, live view of Q2 (right-to-left traversal), as `Q1`.
- Q2 is the sibling-reversed counterpart of Q1.

### Closing cells
A node with children has a closing cell in each list, an unnamed cell directly after the last cell of its subtree; it is created with the node's first child and removed with its last one. The subtree of a node is the block from the node to its closing cell, in Q1 and in Q2, so the end of a block is known without a search. Closing cells take positions like nodes but are never compared with them; reachability compares node cells only.

### `string Source`
Return the symbolic source node.
- Returns the symbolic start marker of all projections.
- This node is **not** part of the tree structure.
- It conceptually acts as the left bracket delimiting Q1 and Q2.

### `string Sink`
Return the symbolic sink node.
- Returns the symbolic end marker of all projections.
- This node is **not** part of the tree structure.
- It conceptually acts as the right bracket delimiting Q1 and Q2.

## Query Methods

### Reachability

#### `bool CanReach(string u, string v)`
Check if one node can reach another.
- Returns `true` if there is a directed path from node `u` to node `v`.
- The check is structural and respects tree hierarchy.
- A name not in the tree, or a handle of a removed node, reaches nothing and is reached by nothing (`false`); with `strict`, it throws instead.

#### `bool CanNotReach(string u, string v)`
Check if one node cannot reach another.
- Returns `true` if there is no directed path from node `u` to node `v`.
- Logical negation of `CanReach(u, v)`.

### Ancestry and Structure

#### `string? NextInQ1(string node)` / `DNode? NextInQ1(DNode node)`
- Returns the node after `node` in Q1, or `null` after the last node. Q1 is the display order of a tree view: parents before children, siblings in insertion order. Passes over the closing cells of the subtrees that end after `node`: O(1) amortized over a walk through Q1. Python: `next_in_q1(node)` (`None`).

#### `string SubtreeLast(string node)` / `DNode SubtreeLast(DNode node)`
- Returns the last node of the subtree of `node` in Q1; the subtree is the contiguous block from `node` to it.
- Goes back from the closing cell of `node` over the closing cells that precede it: O(length of the path of last children below `node`). Insertions, deletions and moves do not need it; they use the closing cell directly.
- Python: `subtree_last(node)`.

#### `bool IsRoot(string node)`
- Returns `true` if `node` is the root of the tree; `false` for `null` or a name not in the tree (with `strict`, it throws for these).

#### `bool IsLeaf(string node)`
- Returns `true` if `node` has no outgoing edges.

#### `bool IsAncestor(string u, string v)`
- Returns `true` if node `u` lies on the path from the root to node `v`.

#### `bool IsDescendant(string u, string v)`
- Returns `true` if node `u` lies below node `v` in the tree.
- Equivalent to `IsAncestor(v, u)`.

#### `bool SameSubtree(string u, string v)`
- Returns `true` if both nodes share the same root.
- Useful for validating `CutNPaste` targets.

#### `int SubtreeSize(string node)`
- Returns the size (inclusive) of the subtree rooted at `node`.
- Includes the node itself and all its descendants.

#### `int Depth(string node)`
- Returns the distance from the root to `node`.
- The root has depth 0.

#### `List<string> PathToRoot(string node)`
- Returns the sequence of nodes on the path from `node` to the root.
- The last entry in the list is the root itself.

#### `List<string> RootToPath(string node)`
- Returns the sequence of nodes on the path from the root to `node`.
- The first entry in the list is the root itself.

### And/or Queries on the Topology

"u reaches all of S" is a conjunction (and), "u reaches some of S" a disjunction (or); likewise for "reached by". A constructed node stands for a set of nodes S (E. Olgac, "Topology and Structure of Directed Graphs - Inducing a Subgraph," 2021): the minimum (`VMin`, `UMin`) or maximum (`VMax`, `UMax`) of each index over S, separately in Q1 and Q2. `V` means S takes the target role, `CanReach(u, S)`; `U` means the source role, `CanReach(S, v)`. A constructed node stores members, not positions, and stays valid while nodes are inserted; after a deletion or a `CutNPaste` it is recomputed on its next use. Members are nodes, not names: a member that was deleted stays out of the set, even if a new node with the same name is inserted later. All methods accept names or `DNode` handles. See [and-or-queries.md](and-or-queries.md).

#### `VMin VMin(IEnumerable<string> nodes)`, `VMax VMax(…)`, `UMin UMin(…)`, `UMax UMax(…)`
- Build the constructed node of `nodes`; each also takes `IEnumerable<DNode>`.
- Python: `t.vmin(nodes=())`, `t.vmax(…)`, `t.umin(…)`, `t.umax(…)`.

#### `ConstructedNode Add(string node)`
- Adds a node to the set, in O(log k) for k members; returns the constructed node. Python: `add(node)`.

#### `ConstructedNode Discard(string node)`
- Removes a node from the set; no error if it is not a member. Returns the constructed node. O(k) for k members; if the node held the minimal (or maximal) position in Q1 or Q2, the other members are scanned for the new one. Typical use: expanding a node in a tree view whose collapsed nodes are kept as a `UMin`. Python: `discard(node)`.

#### `bool Contains(string node)`
- Returns `true` if the node is a member of the set. O(1). Python: `node in s`.

#### `string? UMin.Covering(string v)` / `DNode? UMin.Covering(DNode v)`
- Returns the topmost member of the set that reaches `v`, or `null` if no member does. O(log k). With the collapsed nodes of a tree view as a `UMin`, this is the visible row that contains `v`; `null` means `v` itself is visible. Python: `covering(v)` (`None`).

#### `bool VMin.ReachesAll(string u)`
- Returns `true` if `u` reaches every node of the set: `u` lies left of VMin in both Q1 and Q2. O(1).
- Vacuously `true` for an empty set. Python: `reaches_all(u)`.

#### `bool VMax.MayReachSome(string u)`
- O(1) filter: `false` means `u` reaches no node of the set; `true` is not a confirmation. Python: `may_reach_some(u)`.

#### `bool VMax.ReachesSome(string u)`
- Returns `true` if `u` reaches at least one node of the set. Exact, O(log k): the first member after `u` in Q1 is found by binary search and tested, since the subtree of `u` is the block directly after `u` in Q1.
- `false` for an empty set. Python: `reaches_some(u)`.

#### `bool UMax.ReachedByAll(string v)`
- Returns `true` if every node of the set reaches `v`: `v` lies right of UMax in both Q1 and Q2. O(1).
- Vacuously `true` for an empty set. Python: `reached_by_all(v)`.

#### `bool UMin.MayBeReachedBySome(string v)`
- O(1) filter: `false` means no node of the set reaches `v`; `true` is not a confirmation. Python: `may_be_reached_by_some(v)`.

#### `bool UMin.ReachedBySome(string v)`
- Returns `true` if at least one node of the set reaches `v`. Exact, O(log k): UMin keeps the topmost members (no ancestor in the set) in Q1 order; their subtrees are disjoint, so only the last topmost member before `v` in Q1 needs testing.
- `false` for an empty set. Python: `reached_by_some(v)`.

#### `MemberNames`, `IndexNodes`, `Count`, `Refresh()`
- The members in Q1 order; the members holding the minimal or maximal index in Q1 and in Q2 (possibly two different nodes); the number of members; an explicit recomputation (normally automatic). Python: `members`, `index_nodes`, `len(x)`, `refresh()`.
