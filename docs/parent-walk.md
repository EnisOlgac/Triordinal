# The Parent Walk's Home Ground

Classical trees link every node to its parent, and usually to its children as well. To find out whether *u* is an ancestor of *v*, a program climbs from *v* towards the root and checks whether it meets *u*: the *parent walk*. It needs no preparation and no extra memory, and inserting a node costs one link. This page says where it is the right tool, where it stops being one, and how the benchmarks show both.

## Bottom-up questions, at the cost of the depth

From any node, a parent link leads only upwards. Everything the walk can answer is a question about the path above a node:

- the parent of *v*;
- whether *u* is an ancestor of *v* (`can_reach(u, v)`): climb from *v* and look for *u*;
- the depth of *v* and its path to the root;
- the lowest common ancestor of two nodes, by climbing from both;
- whether some member of a set lies above *v* ("reached by some"), by climbing once and looking each ancestor up in a hash set.

Each costs up to the depth of *v*. Enis Olgac's observation is the point of this page: the walk succeeds because the search runs bottom-up, and it is confined to that direction.

## Depth decides, not size

The cost of a walk is the number of ancestors, not the number of nodes. A tree of a million nodes that is ten levels deep is answered in at most ten steps; a chain of ten thousand needs up to ten thousand. In the benchmarks, the trees are built from a chain ("spine") of the given depth with all other nodes attached at random to spine nodes, so adding nodes makes a tree wider, not deeper. In the table with static pre/post numbers, for example, 5,000 nodes at depth 100 still mean at most 100 steps per walk.

`DTree` answers `can_reach` in O(1) at every depth. An insertion, however, costs two list insertions with fractional positions (and registering the node's name) instead of one link. That gives the walk its home ground:

- **Shallow trees.** At a depth of about 10, ten parent steps are cheaper than anything else, including `DTree`'s insertion. The walk wins there whatever the mix of operations.
- **As many writes as reads.** With one query per insertion, `DTree` pays for the insertion without many queries to spread it over. The crossover lies at a depth of a few hundred in Python and higher in C#, where pointer chasing is cheap.

With more queries per change, the crossover moves towards shallow trees. With ten queries per insertion, `DTree` is ahead from depth 100 in Python and from depth 1,000 in C# (see the measurements below).

## Out of reach for the walk

A parent link knows nothing about what lies below a node or beside it. Questions of that kind are top-down or about order, and the walk cannot answer them at all; a program has to add structure (child lists, sibling links, traversal numbers) and pay for it:

- **Subtrees.** What lies under *u*, how large is it, where does it end? With child lists this costs the size of the subtree; `DTree` finds the end of a subtree with `subtree_last`, usually in O(1).
- **Order.** Which of two nodes comes first in the display order, and which rows follow a given row in a tree view? `DTree`'s Q1 is the display order.
- **"Reaches some" over a set.** Whether *u* reaches some member of *S* has no bottom-up answer except climbing from every member, O(*k* · depth); `DTree` answers it in O(log *k*) (see [and/or queries on the topology](and-or-queries.md)).
- **Static numbers do not help under changes.** Pre/post numbers from a traversal answer ancestor questions in O(1) and give the order, but each insertion invalidates them; recomputing them makes *n* insertions cost O(*n*²).

## Use case: a tree view with expand/collapse

A tree view shows each collapsed node as a single row and hides its subtree. The benchmark runs both representations through the same sequence of steps. Each step first changes the tree, half the time inserting a leaf and half the time collapsing or expanding a node. It then shows a random node *v*:

1. Find the visible row that contains *v*: *v* itself, or its topmost collapsed ancestor.
2. List the next 20 visible rows from there, skipping the subtree of every collapsed node.

The two contenders:

- **Classical model:** parent link, child list, next-sibling link and a collapsed flag per node. Step 1 climbs from *v* to the root. Step 2 takes the first child of an expanded node, otherwise the next sibling of the node or of its nearest ancestor that has one.
- **`DTree`:** the collapsed nodes are one `UMin`. Step 1 is `collapsed.covering(v)`, O(log *k*) for *k* collapsed nodes. Step 2 follows Q1 with `next_in_q1` and jumps over each collapsed node's subtree with `subtree_last`. Expanding a node is `collapsed.discard(node)`, collapsing it `collapsed.add(node)`.

Both produce the same rows in every step; the benchmark checks this. The classical model pays for the climb in step 1 at every depth, and in step 2 whenever it has to climb back to find a next sibling. `DTree` pays the same at every depth.

## Measurements

Measured by Enis Olgac on his NUC (Windows) with DTree 1.7.0, Python 3.14.2 and .NET 9.0.21. Each figure is the best of three runs. The trees are built from a spine of the given depth, as described above; C# uses node handles. Factors above 1 mean `DTree` is faster.

### Dynamic updates

A step is one insertion followed by 1 or 10 queries between random nodes present at that moment, in µs per step. Python: 20,000 nodes; C#: 100,000 nodes.

| depth | Python: DTree, 1 query | walk | factor | DTree, 10 queries | walk | factor |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 2.08 | 0.30 | 0.1× | 4.60 | 2.76 | 0.6× |
| 100 | 2.52 | 1.49 | 0.6× | 4.71 | 13.4 | 2.8× |
| 1,000 | 4.02 | 12.5 | 3.1× | 7.40 | 127 | 17× |
| 10,000 | 3.12 | 88.1 | 28× | 7.49 | 1,027 | 137× |

| depth | C#: DTree, 1 query | walk | factor | DTree, 10 queries | walk | factor |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 1.12 | 0.096 | 0.1× | 1.57 | 0.44 | 0.3× |
| 100 | 1.00 | 0.23 | 0.2× | 1.29 | 1.00 | 0.8× |
| 1,000 | 1.29 | 1.21 | 0.9× | 1.75 | 10.1 | 5.8× |
| 10,000 | 1.66 | 13.5 | 8.2× | 2.47 | 111 | 45× |
| 100,000 | 1.47 | 69.6 | 47× | 1.59 | 729 | 458× |

`DTree`'s time per step barely depends on the depth; ten queries instead of one add a few µs in Python and well under one in C#. The walk's time grows with the depth and with the number of queries. On shallow trees the walk wins in both languages; with one query per insertion the crossover lies between depths 100 and 1,000 in Python and near 1,000 in C#.

### Static pre/post numbers

One query per insertion; the numbers are recomputed by a traversal before the next query. Total time in ms.

| depth | nodes | Python: DTree | walk | static numbers | nodes | C#: DTree | walk | static numbers |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 1,000 | 1.7 | 1.2 | 224 | 1,000 | 0.4 | 0.1 | 18 |
| 100 | 2,000 | 3.6 | 2.6 | 911 | 10,000 | 5.2 | 1.1 | 535 |
| 100 | 5,000 | 10.0 | 6.6 | 5,711 | 20,000 | 10.6 | 1.9 | 2,475 |
| 1,000 | 1,000 | 1.6 | 4.4 | 222 | 1,000 | 0.2 | 0.3 | 4 |
| 1,000 | 2,000 | 5.2 | 14.6 | 878 | 10,000 | 4.0 | 9.1 | 571 |
| 1,000 | 5,000 | 10.6 | 51.1 | 5,834 | 20,000 | 17.8 | 20.3 | 2,609 |

At depth 100 the walk is faster than `DTree`; at depth 1,000 the order is reversed in Python and nearly even in C#. In both languages, doubling the number of nodes roughly quadruples the time of the static numbers, whatever the depth: O(*n*²) for *n* insertions, against O(*n*) for the other two. (Runs of 1,000 nodes in C# are too short to be measured reliably.)

### Tree view with expand/collapse

µs per step, as described in the use case above. Python: 20,000 nodes and 5,000 steps; C#: 100,000 nodes and 20,000 steps.

| depth | Python: DTree | classical | factor | C#: DTree | classical | factor |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 6.3 | 1.5 | 0.2× | 1.22 | 0.25 | 0.2× |
| 100 | 6.0 | 2.8 | 0.5× | 0.80 | 0.37 | 0.5× |
| 1,000 | 7.9 | 19.3 | 2.4× | 1.01 | 1.63 | 1.6× |
| 10,000 | 5.2 | 186 | 36× | 1.88 | 13.0 | 6.9× |
| 100,000 | — | — | — | 4.86 | 226 | 46× |

The classical model wins up to depth 100 in both languages; from depth 1,000 on, `DTree` is ahead, and the gap grows with the depth. The classical model never loses correctness, only speed: every step climbs to the root to find the topmost collapsed ancestor.

## Choosing: the mill horse and the navigator

The parent walk is a passive view. Like a horse turning a mill, it walks the one path it is harnessed to, step by step towards the root. It sees only the next step, and it learns whether the target was on the path only when it gets there or runs out of path. Every question sends it round again, and the deeper the tree, the longer the round. For a shallow tree and questions about what lies above a node, this is honest, cheap work, and nothing beats it.

`DTree` is passive and active. It can walk the same path (`get_parent`, `path_to_root`), but its two positions also tell it where a target lies before it takes a step: left or right of a node in Q1 and Q2, inside or outside a block. So it can act on the answer:
- jump over a whole subtree (`subtree_last`);
- pick the one member of a set worth testing (binary search in `reaches_some`, `covering`);
- go straight to the next visible row (`next_in_q1`).

Which one to use depends on two things:

- **What the user will do.** Only reading upward (parents, ancestors, depth): the walk suffices. Navigating, selecting, collapsing and expanding, asking about subtrees, order or sets: these need the active side, and the walk cannot answer them on its own.
- **How shallow the tree is.** On trees of depth around 10, the walk's rounds are short enough to beat any encoding. As depth grows, each round grows with it, while `DTree`'s cost stays the same.

The distinction between the passive view and the active one, and the picture of the mill horse, are Enis Olgac's.

## Reproducing

```
python -m triordinal.dtree.bench --dynamic                                        # dynamic updates and the tree view
dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench dynamic
```

Without `--dynamic` (or `dynamic`), the full benchmark runs, including these sections. Every run writes a Markdown report to `benchmarks/python/` or `benchmarks/csharp/`.
