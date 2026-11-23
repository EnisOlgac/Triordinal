# One List and Two Lists

This page was written for DTree 2.x, which encoded a tree in two ways with the same API: `EulerTree` on one list, `DTree` on two (since 3.0.0 `triordinal.dtree.two_lists.DTree`). For trees both answer the same queries with the same results. The page explains how they differ in what they store and what that difference costs, and ends with [the way to DTree 3.0](#the-way-to-dtree-30), which came out of this comparison.

## Containment and topology

`EulerTree` encodes **containment**. A node's subtree is the block from its own cell to its closing cell, and *u* reaches *v* when *v* lies strictly inside *u*'s block. Two blocks are either nested or disjoint.

`DTree` encodes **topology**. `Q1` and `Q2` are two orders of the nodes, the pre-order with siblings left to right and with siblings right to left, and *u* reaches *v* when *u* precedes *v* in both: the product order of `Q1` and `Q2`. `DTree` is the natural view of a tree.

For a tree, the two are the same relation, and they differ in one thing only: the delay between a node's own cell and the end of its subtree. Containment has to store it; topology implies it. In a directed graph they are no longer the same relation (see [Graphs](#graphs)).

## Where is the next branch?

The crucial question is where the next branch begins: the first node after *u*'s subtree in `Q1` (*u*'s next sibling, or the next sibling of the nearest ancestor that has one). It is what a new child, a moved subtree or a jump over a collapsed node needs.

**One list.** A pre-order alone does not determine the tree: `a b c` may be a chain or a star. The delay between a node's own cell and the next branch is the size of its subtree, and nothing in the node's own position tells that size. So it has to be stored: in `EulerTree` the closing cell *is* that information. The next branch follows the closing cell, after any further closing cells, one for each level that ends there.

**Two lists.** `Q1` and `Q2` hold the next branch by themselves, in three ways:

- *By walking `Q1`.* Every node of *u*'s subtree comes after *u* in `Q2`, and the next branch comes before it: the next branch is the first node after *u* in `Q1` that precedes *u* in `Q2`.
- *By the spine in `Q2`.* After *u* in `Q2` come *u*'s last child, that child's last child, and so on: the right spine of *u*'s subtree. While `Q1` keeps rising from one node to the next, the iteration is on the spine; the last node before `Q1` falls is the last node of *u*'s subtree in `Q1`, and the next branch follows it. This passes only the spine, not the subtree.
- *By ranks.* With 1-based ranks in a tree of *n* nodes, the last node of *u*'s subtree has the `Q1` rank *n* + 1 − `Q2`(*u*) + depth(*u*), and the next branch the rank after it. This is the classical identity of pre- and post-order numbers (post = pre + size − depth − 1), written for `Q2`, which is the post-order reversed.

Example (insertions a→b, a→c, a→d, b→e, b→f, d→g; *n* = 7):

```
Q1 = a b e f c d g
Q2 = a d g c b f e
```

| node | `Q1` | `Q2` | depth | 8 − `Q2` + depth | last node of its subtree | next branch |
|---|---|---|---|---|---|---|
| a | 1 | 1 | 0 | 7 | g | none |
| b | 2 | 5 | 1 | 4 | f | c |
| e | 3 | 7 | 2 | 3 | e (a leaf) | f |
| f | 4 | 6 | 2 | 4 | f (a leaf) | c |
| c | 5 | 4 | 1 | 5 | c (a leaf) | d |
| d | 6 | 2 | 1 | 7 | g | none |
| g | 7 | 3 | 2 | 7 | g (a leaf) | none |

Walking `Q1` from b: e (`Q2` 7) and f (6) follow b (5) in `Q2`; c (4) precedes it, so c is the next branch. By the spine: after a in `Q2` come d (`Q1` 6) and g (7), then c (5) falls, so a's subtree ends at g; after b comes f (4), then e (3) falls, so b's subtree ends at f; after the leaf c, b (2) falls at once. In `EulerTree`, the same step from f passes b's closing cell before it reaches c.

So in `EulerTree` the closing cell is information; in `DTree` it is a shortcut.

## Compared with a classical tree

A classical tree with parent, child and sibling links has constant-time operations only for what is local to a node; everything that concerns the topology climbs or descends:

| operation | classical tree | `EulerTree` | `DTree` |
|---|---|---|---|
| parent, first child, next sibling, leaf test | O(1) | O(1) | O(1) |
| insert a child | O(1) | O(1) | O(1) |
| does *u* reach *v*? | O(depth): climb from *v* | O(1): two comparisons | O(1): two comparisons |
| where is the next branch? | O(depth): climb to the nearest ancestor with a next sibling | the closing cell, then one step per further level closed | the same with closing cells; without, by the spine in `Q2` |
| does *u* reach all of *S*? | O(k · depth) | O(1) per query, after building the constructed node in O(k) | the same |

Where the classical tree is enough, and where it is not, is measured in [the parent walk's home ground](parent-walk.md).

## Blind and navigated traversal

**Upward**, toward the root, there is nothing to choose: every node has one parent. A classical tree climbs its parent links; to learn whether *u* is an ancestor of *v*, it climbs from *v* until it meets *u* or reaches the root, and knows the answer only on arrival. The encoded trees know it before the first step: two comparisons.

**Downward** there is a choice at every node: which child leads to the target? `DTree` needs no search for it. The path from *u* to a target *t* consists of the nodes between them in `Q1` that can reach *t*, and each of them, coming before *t* in `Q1`, can reach *t* exactly when it precedes *t* in `Q2`. So iterating `Q1` from *u* to *t* and selecting the nodes that precede *t* in `Q2` gives the path, forward; iterating from *t* back to *u* gives it backward. One comparison per node, with no traversal, lookup or parent link. Toward a set of targets, the constructed nodes tell for each node whether it reaches some or all of them.

`EulerTree` can select the same nodes, but its test is containment: a node can reach *t* when *t* lies inside its block, which needs the node's closing cell.

The classical tree can obtain the same path, but only from the target: with parent links it first climbs from the target to the start and then follows the recorded path back; with child links alone it has to search the subtrees. Toward a set, it climbs from every member.

Example, in the tree above: from a to f, `Q1` passes b (`Q2` 5) and e (7); only b precedes f (6) in `Q2`, so the path is a, b, f. From a to g (`Q2` 3), `Q1` passes b (5), e (7), f (6), c (4) and d (2); only d is selected: a, d, g. The classical tree first climbs from the target, f → b → a.

Navigation separates the encoded trees from the classical tree. Between the two encodings it is the same difference again: `DTree` selects the path from the nodes' own positions, `EulerTree` from their blocks.

## Why DTree has closing cells anyway

The lists keep positions, not ranks. Only the order of two positions carries meaning, never their difference: a new position is placed between its neighbors by the order of insertions, so the gap between two nodes says nothing about how many nodes lie between them. The walks above use only the order; the rank formula needs counts. Counts could come from equidistant positions, but keeping them equidistant moves every later node at each insertion, O(n); this is the extreme case of the list-labeling trade-off, where the less room the labels leave, the more must be relabeled. Otherwise ranks need an order-statistic structure (a balanced tree with subtree counts), which makes every rank, and so every comparison, O(log n), and the depth of every node, which `cut_n_paste` changes for a whole subtree. Even with the rank of the end, its cell still has to be reached.

Insertion needs the end of a subtree: a new child goes directly after its parent in `Q2`, but after the parent's whole subtree in `Q1` (with siblings reversed, a new child is at the near end in one list and at the far end in the other). Three ways to find that end:

| | cost of finding the end | extra memory and upkeep |
|---|---|---|
| closing cells (since 2.1.0) | O(1) | one cell per node with children, in each list; created with the first child, removed with the last |
| the spine in `Q2` | one step per node on the right spine of the parent's subtree: none under a leaf, long only above a deep last child | none |
| walking `Q1` | O(k) over the parent's subtree | none |
| ranks and depth | O(log n), and O(log n) for every comparison | an order-statistic structure and the depths |

`DTree` uses closing cells, as proposed in the review of DTree 1.8.0, for constant-time insertion. Before 2.1.0 it walked, shortened by a validated hint with path compression. Reachability itself never uses them in `DTree`: it compares the nodes' own positions in `Q1` and `Q2`. A `DTree` without closing cells, ending subtrees by the spine in `Q2`, would save their memory and upkeep and pay per node on the spine; it has not been measured yet.

## Housekeeping

What a node carries in the current implementation:

- its cells: `c1` (and `c2` in `DTree`), and while it has children its closing cells `e1` (and `e2`); every cell refers back to its node, so a closing cell leads to the node whose block it closes;
- a leaf has no closing cell: its block is its own cell (`e1 or c1`), so a leaf's first child costs two insertions per list, the child's cell and the new closing cell;
- a parent link and a children list, shared by both classes. Neither encoding needs them for reachability; the sibling order is in the lists as well.

`DTree` carries the cells twice. The benchmarks ([`prior-art.md`](prior-art.md)) measure the implementations with all of this, not the bare encodings: in C#, `DTree` takes about 1.5 to 2.5 times `EulerTree`'s update time and a third more memory, while answering queries as fast.

## The way to DTree 3.0

The comparison above leaves one question: if two orders imply the end of a block and one list has to store it, does the end have to be stored at all? DTree 3.0 (design by Enis Olgac, November 2026) answers no. It keeps one projection, `Q1`, and the structure in the vertices: a vertex knows its parent, its kids list (read left to right from one end and right to left from the other, so the sibling-reversed order is at hand without a second list), its handle in its parent's kids list, and its cell in `Q1`.

The end of a block is then neither stored nor computed from ranks: the next branch of *u* is its right sibling, or, if *u* is the last kid, the next branch of its parent. The block is a difference list whose tail is that delimiter. The climb to the delimiter is the closing-parenthesis procedure of the Euler tour, done only when it is needed, and the query rarely needs it: it is decided as a cascade of local steps (*v* not after *u*; *u* without kids; *u*'s right sibling; *u*'s last kid), and only 2 to 3 queries in 100 go further in random and reading-order trees. A sequence of only kids, where the climb would be long, is crossed in one step as a *vertical run*.

So DTree 3.0 has neither `Q2` nor closing cells, and so none of the housekeeping listed above: in C# about 280 bytes per node against 380 to 460 for `EulerTree` and 520 to 630 for DTree 2.x, building faster, querying as fast. See the [README](../README.md#structure) and [`API.md`](API.md).

## Graphs

In a directed graph the descendants of two vertices can overlap without nesting, which containment cannot represent. The smallest example is a → c, b → c, b → d: the descendants of a, {c}, and of b, {c, d}, overlap, so no single list encodes them. Two orders do:

```
Q1 = a b c d
Q2 = b d a c
```

`DTree` builds trees only; it does not insert the edge b → c. DGraph, planned in this repository, will maintain such orders for directed graphs.
