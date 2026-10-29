# DTree Public API Reference

*Markdown edition of [`User.Doc.pdf`](User.Doc.pdf).*

## Overview

The `DTree` class represents a symbolic directed tree with a unique root and internal support for dual projections (Q1 and Q2). Each node is identified by a unique string. Edges are added incrementally, and projections are updated automatically. Structural operations preserve the tree's topological validity.

## Constructor

### `DTree(string id)`
Create a new tree with a given identifier.
- Initializes a new directed tree with the given identifier.
- The root is determined implicitly as the source of the first inserted edge.
- Q1 and Q2 projections are initialized automatically.

## Core Methods

### `void Insert(string parent, string child)`
Insert a new edge into the tree.
- Adds a directed edge from `parent` to `child`.
- The `parent` must already exist in the tree.
- The `child` must not already exist.
- Updates Q1 and Q2 projections accordingly.
- The new node becomes the **last** child of `parent`.

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
- Python: `add_line(line)`.

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

### `DList Q1`
Return the Q1 projection.
- Returns a copy of the Q1 projection (left-to-right traversal).
- The projection reflects the current visible tree state.

### `DList Q2`
Return the Q2 projection.
- Returns a copy of the Q2 projection (right-to-left traversal).
- Q2 is the sibling-reversed counterpart of Q1.

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

#### `bool CanNotReach(string u, string v)`
Check if one node cannot reach another.
- Returns `true` if there is no directed path from node `u` to node `v`.
- Logical negation of `CanReach(u, v)`.

### Ancestry and Structure

#### `string? NextInQ1(string node)` / `DNode? NextInQ1(DNode node)`
- Returns the node after `node` in Q1, or `null` after the last node. Q1 is the display order of a tree view: parents before children, siblings in insertion order. O(1). Python: `next_in_q1(node)` (`None`).

#### `string SubtreeLast(string node)` / `DNode SubtreeLast(DNode node)`
- Returns the last node of the subtree of `node` in Q1; the subtree is the contiguous block from `node` to it.
- A short walk down the last children finds it on ordinary trees; beyond that, the end remembered last time is reused when it validates in O(1) (it lies in the subtree and its Q1 successor does not). Asked again for the same node, it is usually O(1).
- Python: `subtree_last(node)`.

#### `bool IsRoot(string node)`
- Returns `true` if `node` is the root of the tree.

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

"u reaches all of S" is a conjunction (and), "u reaches some of S" a disjunction (or); likewise for "reached by". A constructed node stands for a set of nodes S (E. Olgac, "Topology and Structure of Directed Graphs - Inducing a Subgraph," 2021): the minimum (`VMin`, `UMin`) or maximum (`VMax`, `UMax`) of each index over S, separately in Q1 and Q2. `V` means S takes the target role, `CanReach(u, S)`; `U` means the source role, `CanReach(S, v)`. A constructed node stores members, not positions, and stays valid while nodes are inserted; after a deletion or a `CutNPaste` it is recomputed on its next use. All methods accept names or `DNode` handles. See [and-or-queries.md](and-or-queries.md).

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
