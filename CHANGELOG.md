# Changelog

## 2.0.0

Archived on Zenodo: doi:10.5281/zenodo.23760809.

**Triordinal continues DTree.** The code of DTree 1.8.0 moves to this repository, split into packages so that DGraph can join later without depending on DTree:

| Package | Python | NuGet | Depends on |
|---|---|---|---|
| DList: the list with rational positions | `triordinal-dlist`, `from triordinal.dlist import DList` | `Triordinal.DList`, namespace `Triordinal` | nothing |
| DTree | `triordinal-dtree`, `from triordinal.dtree import DTree` | `Triordinal.DTree`, namespace `DirectedTrees` | DList |

- The previous Python import name `dtree` clashed with an unrelated package on PyPI (dtree 0.2.3, a decision-tree library from 2014); `triordinal.dtree` does not.
- DTree and the future DGraph share only DList; neither depends on the other, so each can carry its own license. DList and DTree are MIT.
- C#: a list cell refers to its owning node as `object` instead of `DNode`, so DList knows nothing of DTree. Projects `csharp/Triordinal.DList`, `csharp/Triordinal.DTree`, `csharp/Triordinal.DTree.Tests`; the benchmark runs as `python -m triordinal.dtree.bench`.
- Python 3.9 or later (CI tests 3.9, 3.12 and 3.13).

**Fixes in DList** (reported in Onur Safi's review of DTree 1.8.0; the import name clash was also pointed out by Sinan Emiroğlu):
- C#: 64-bit numerators could overflow. A numerator grows with value times denominator, and values grow with every insertion at an end of the list, deletions never shrinking them; after 6 million insertions at the end, inserting into one gap overflowed, left the cell linked at a wrong position, and the list unsorted. Now a region is also renumbered when a numerator would exceed 2^61, so no mediant can overflow, and a cell is linked only after its position is computed. Python's integers never overflowed.
- Both languages: the markers SOURCE and SINK can no longer be inserted, moved or removed as names (`insert_before("]", "a")` used to unlink SINK and break the list); this raises `ValueError` / `ArgumentException`.

Apart from these fixes the API is unchanged; only the import, package and project names change. Versions 1.0.0 to 1.8.0 remain in [EnisOlgac/DTree](https://github.com/EnisOlgac/DTree), archived on Zenodo (doi:10.5281/zenodo.23395710), and on PyPI as `dtree-encoding` and NuGet as `DTree.Encoding`.

## 1.8.0

Archived on Zenodo: doi:10.5281/zenodo.23685810.

**Inserting siblings at a chosen place** (Python and C#). `insert_after(sibling, child)` / `InsertAfter` puts the new node directly after an existing sibling, `insert_before(sibling, child)` / `InsertBefore` directly before it, with the same parent. Until now a new node always became the last child. Both are two local list insertions, like `insert`: in Q1 after the end of the sibling's subtree (or directly before the sibling), in Q2 directly before the sibling (or after the end of its subtree there). No other node moves, and constructed nodes stay valid. Inserting before a first child walks down the first children in Q2 to find the end of its subtree.

The description format of the `.csx` files gets two new operators, `s > c1; c2` and `s < c1; c2`, next to `p: c1; c2` (suggested by Enis Olgac). `add_line(line)` / `AddLine` applies one such line; `from_file` / `FromFile` and the Tree.View viewer use it.

## 1.7.0

Archived on Zenodo: doi:10.5281/zenodo.23437422.

**Removing members from a constructed node** (Python and C#). `discard(node)` / `Discard(node)` takes a node out of the set again, and `node in s` / `Contains(node)` tests membership. If the removed node held the minimal (or maximal) position in Q1 or Q2, the remaining members are scanned for the new one, O(k); `UMin` also rebuilds its list of topmost members when one of them is removed. With this, the collapsed nodes of a tree view can be kept as one `UMin` across expand and collapse. Listed as an open point by Enis Olgac.

**Tree views.** Two methods for showing a tree with collapsed nodes: `UMin.covering(v)` / `Covering(v)` returns the topmost member of the set that reaches `v`, O(log k)—with the collapsed nodes as a `UMin`, the visible row that contains `v`—and `next_in_q1(node)` / `NextInQ1(node)` returns the next node in Q1, the display order. `discard` now finds the member by binary search.

**The parent walk's home ground.** New page [`docs/parent-walk.md`](docs/parent-walk.md): the parent walk answers bottom-up questions (Enis Olgac's observation), at a cost that depends on the depth of the tree, not its size. It wins on shallow trees with as many writes as reads, and cannot answer top-down or order questions. The benchmarks now show this directly:
- dynamic updates with 1 and with 10 queries per insertion;
- static pre/post numbers at depths 100 and 1,000;
- a tree-view use case, in which every step inserts a leaf or collapses or expands a node, then finds the visible row of a random node and lists the next 20 visible rows, against a classical model with parent, child and sibling links.

Each dynamic measurement is the best of three runs, which removes the warm-up effect from the first row. Requested by Enis Olgac after reviewing the 1.7.0 benchmark reports.

Measured by Enis Olgac on his NUC (tables in `docs/parent-walk.md`): in the tree view, the classical model wins up to depth 100; from depth 1,000 on, `DTree` is ahead, by 36× at depth 10,000 in Python and 46× at depth 100,000 in C#. With ten queries per insertion, `DTree` leads the parent walk by up to 137× in Python (depth 10,000) and 458× in C# (depth 100,000).

**Benchmarks in the Python package.** `python -m dtree.bench` runs the full benchmark after `pip install dtree-encoding`, without a clone of the repository, and writes the report to `benchmarks/python/` in the current directory; inside a clone it still goes to the repository root. `python/benchmarks/bench.py` is now a thin wrapper around it. Suggested by Enis Olgac: users should be able to measure on their own machines.

- Benchmarks write a Markdown report for every run: `benchmarks/python/` and `benchmarks/csharp/` at the repository root, file name from date and time (e.g. `2026-10-17_14-18.md`; no colons, as Windows does not allow them in file names). The header records the DTree, Python or .NET version, the operating system, the processor and the command; `--note "…"` adds a remark such as the machine's state, `--no-save` skips the report. Suggested by Enis Olgac.
- The C# benchmarks now print numbers in the invariant format (10,000 and 0.013), like the Python ones, whatever the system's language settings.

## 1.6.0

Archived on Zenodo: doi:10.5281/zenodo.23434347.

**Node handles in Python.** As in C# since 1.3.0, `insert` returns a `DNode` handle, `get_node(name)` and `try_get_node(name)` give the handle of an existing node, and every method accepts a handle wherever it accepts a name (including the and/or queries). A handle refers directly to the node's positions in Q1 and Q2, so `can_reach` on handles is two position comparisons without any lookup by name; the idea of using addresses as ids comes from Enis Olgac's original implementation, and placing the positions on the vertices was his suggestion. Internally, parents and children are now kept as direct references, so queries by name also got faster (two dictionary lookups instead of six). The name-based API is unchanged.

**End of a subtree without the worst case** (Python and C#). A new child goes after the last node of its parent's subtree in Q1; that node was found by walking down the last children, which is O(depth) per insertion in adversarial shapes. Now a short walk (8 steps) handles ordinary trees as before, and beyond it the end remembered last time is reused when it validates in O(1) with DTree's own order (it lies in the subtree and its Q1 successor does not); otherwise the walk continues with path compression. Stale hints are detected, never used, so ancestors need no update when a subtree grows—the recursive update of delimiters that Enis Olgac had observed in earlier designs is avoided. Enis asked for a middle way between computing the end and storing it; the validated hint is Claude's design, chosen after measuring three variants (see the design notes). New public method `subtree_last(node)` / `SubtreeLast(node)`. The benchmarks gain a "top-down comb" shape (a chain of 3,000, then new leaves under the spine nodes from the top down), where the plain walk needs 4.5 million steps for 30,000 nodes.

**Wording.** "Set queries" are now called **and/or queries on the topology**, which says what they ask: whether a vertex reaches all (and) or some (or) of a set of vertices, or is reached by all or some of them. `docs/set-queries.md` moved to [`docs/and-or-queries.md`](docs/and-or-queries.md); the old file remains as a pointer. The term *topology* now appears in the first sentence of the README, the package descriptions on PyPI and NuGet, and their keywords (wording by Enis Olgac).

Tests: handles, and/or queries with handles, the top-down comb, and random sequences of inserts mixed with deletes and moves checked against the brute-force reference, once with the normal budget and once with the hint used on every insertion.

Measured on Enis Olgac's NUC (`bench.py`, `-- bench`), compared with the 1.4.1 runs on the same machine:

| | 1.4.1 | 1.6.0 |
| --- | ---: | ---: |
| Python `can_reach`, random tree of 100,000 nodes, by name | 1.4 µs | 0.9 µs |
| Python `can_reach`, by handle | — | 0.5 µs |
| C# `CanReach`, by name / by handle | 0.19 / 0.05 µs | 0.18 / 0.05 µs |
| Python, building the top-down comb of 100,000 nodes | — | 0.23 s (random: 0.34 s, chain: 0.43 s) |
| C#, building the top-down comb of 100,000 nodes | — | 0.18 s (random: 0.24 s, chain: 0.17 s) |
| Python dynamic step (insert + query, handles), depth 1,000 / 10,000 | 3.4 / 3.9 µs | 2.6 / 2.9 µs |

The top-down comb now builds as fast as the ordinary shapes; with the plain walk it would take about 4.5 million walk steps (3,000²/2 in its first round). In C#, which already had handles, the other figures are unchanged within measurement noise, as expected: the hint only matters in shapes like the comb. Two values in the Python run stand out as one-off disturbances (dynamic step at depth 100: 7.4 µs; static-numbers table, 1,000 nodes: 24 ms for DTree); the tables in `docs/and-or-queries.md` are from 1.4.1 and labeled so.

## 1.5.0

Archived on Zenodo: doi:10.5281/zenodo.23426313.

**Packages.** DTree is now installable from the package managers; the library itself is unchanged.

- Python: `pip install dtree-encoding` (PyPI), imported as `dtree`.
- C#: `dotnet add package DTree.Encoding` (NuGet), namespace `DirectedTrees`.
- The names carry the subject of the paper, the encoding of the topology. A new workflow (`.github/workflows/publish.yml`) tests, builds and uploads both packages whenever a GitHub release is published, next to the Zenodo archive; it checks that the package versions match the release tag.
- README: installation section and package badges; the Python README doubles as the PyPI page, the new `csharp/DTree.Core/README.md` as the NuGet page.

## 1.4.1

Archived on Zenodo: doi:10.5281/zenodo.23421930.

Documentation and benchmarks only; the library is unchanged.

- New benchmark for the dynamic case, insertions and queries alternating (`bench.py --dynamic`, `-- bench dynamic`): DTree against the parent walk over increasing depth, and against static pre/post numbers recomputed after each insertion. On Enis Olgac's NUC (C#, 100,000 nodes, one query per insertion; other processes running, so absolute times are indicative), a step costs DTree 1.6–1.9 µs at every depth; the parent walk takes 0.13 µs at depth 10 and 83 µs at depth 100,000. Static numbers need 2.5 s for 20,000 nodes, against 11 ms for DTree, and grow quadratically. Full tables: [`docs/set-queries.md`](docs/set-queries.md).
- [`docs/set-queries.md`](docs/set-queries.md): the simpler exact way of comparing with each element of a set (suggested by Enis Olgac), a paragraph on dynamic approaches in the literature (link-cut and Euler-tour trees, dynamic LCA, order maintenance), and the general applicability of DTree as the frame for the measurements.

## 1.4.0

Archived on Zenodo: doi:10.5281/zenodo.23420472.

**Set queries with constructed nodes** (Python and C#). A constructed node stands for a node set S: the minimum or maximum of each index over S, separately in Q1 and Q2; the two values usually belong to two different members. VMin and VMax take S as the target of reachability, UMin and UMax as the source. The idea and the names VMin and VMax are Enis Olgac's, from his presentation "Topology and Structure of Directed Graphs - Inducing a Subgraph" (ResearchGate, 2021); the naming by role with UMin and UMax is his as well. This release brings them to the tree library.

- `vmin(S).reaches_all(u)` / `VMin(S).ReachesAll(u)`: exact in O(1).
- `vmax(S).reaches_some(u)` / `VMax(S).ReachesSome(u)`: exact in O(log k); `may_reach_some` / `MayReachSome` is the O(1) filter (a node left of VMax may still reach no member).
- `umax(S).reached_by_all(v)` / `UMax(S).ReachedByAll(v)`: exact in O(1).
- `umin(S).reached_by_some(v)` / `UMin(S).ReachedBySome(v)`: exact in O(log k); `may_be_reached_by_some` / `MayBeReachedBySome` is the O(1) filter.
- The two exact "some" tests were added by Claude. `reaches_some` uses the contiguity of subtrees in Q1: the first member after u in Q1 is reached exactly when any member is. `reached_by_some` keeps the topmost members (no ancestor in S) in Q1 order; their subtrees are disjoint, so only the last one before v in Q1 needs testing.
- A constructed node stores its members, not positions. Insertions and renumbering keep the order of existing nodes, so it stays valid while the tree grows; after a deletion or a move it is recomputed on its next use.
- Tests check every answer against brute force, including counterexamples for both filters, nested members, and random sequences of inserts, deletes and moves.
- Benchmarks (Python and C#) compare with the parent walk of a classical tree, by tree depth and for all four set questions. On a tree of 100,000 nodes and depth 10,000, with a set of 1,000 nodes (Enis Olgac's NUC, C#):

| question | DTree | parent walk | factor |
| --- | ---: | ---: | ---: |
| u reaches v | 0.050 µs | 17.1 µs | 344× |
| u reaches all of S | 0.028 µs | 48.6 µs | 1,745× |
| u reaches some of S | 0.209 µs | 17,018 µs | 81,448× |
| all of S reach v | 0.029 µs | 63.9 µs | 2,173× |
| some of S reach v | 0.126 µs | 56.7 µs | 450× |

  DTree's times do not depend on depth; on shallow trees (depth 10) the parent walk is as fast or faster. Full tables for Python and C#: [`docs/set-queries.md`](docs/set-queries.md).

## 1.3.0

Archived on Zenodo: doi:10.5281/zenodo.23414463.

**Node handles in C#** (`DTree.Core`): `Insert` now returns a `DNode` handle, and every operation also accepts handles (`Insert(DNode, string)`, `CanReach(DNode, DNode)`, `Delete`, `DeleteSubtree`, `CutNPaste`, `IsRoot`, `IsLeaf`, `Depth`, …; `GetNode(name)` and `TryGetNode` give the handle of a named node). A handle refers directly to the node's positions in Q1 and Q2, so a reachability test on handles is two position comparisons with no lookup by name. Inside `DTree`, parents and children are kept as direct references, too; names are only looked up where a method receives a name. The idea of using addresses as ids comes from Enis Olgac's original implementation. Handles of deleted nodes, or of another tree, are rejected or reported as unreachable. The name-based API is unchanged.

Reachability on a random tree of 100,000 nodes, 1,000,000 queries (`dotnet run --project csharp/DTree.Tests -c Release -- bench 10000 100000`, same Windows PC as for 1.2.0):

| `CanReach` per call | 1.2.0 | 1.3.0 |
| --- | ---: | ---: |
| C#, with names | 0.369 µs | 0.181 µs |
| C#, with node handles | — | 0.085 µs |
| Python 1.2.0 / 1.3.0, with names (for comparison) | 1.4 µs | 1.4 µs |

With names, `CanReach` now does two dictionary lookups instead of six; with handles it does none, which makes it about 4× faster than in 1.2.0 and about 16× faster than the Python implementation. Building trees takes as long as in 1.2.0 (random tree of 100,000 nodes: 0.24 s), since every new node is still registered by name; renumbering counts are unchanged.

## 1.2.0

Archived on Zenodo: doi:10.5281/zenodo.23414087.

**C# implementation** (`csharp/DTree.Core`): a port of the Python 1.1.0 implementation with the same API in C# naming and the same rational (mediant) positions, stored as 64-bit numerator/denominator pairs and compared with 128-bit products. A test program (`csharp/DTree.Tests`) mirrors the Python test suite and includes the benchmark (`-- bench`). The automatic checks now also run the C# tests.

**Viewer on the new library:** the WPF viewer (`csharp/Tree.View`) now uses `DTree.Core` instead of the prototype. Invalid lines in a `.csx` file are reported and skipped instead of stopping the program. `DTree.Core` and `DTree.Tests` are part of `csharp/DTree.sln`. The original prototype (`src/Tree`) has been removed from the repository; it remains available in releases 1.0.0 and 1.1.0 and their Zenodo archives.

**Folder renamed:** the C# code moved from `src/` to `csharp/`.

**Title** aligned with the paper: "DTree—Topology and Structure of Directed Trees: An Incremental Encoding".

**Benchmark, Python and C#** (`python python/benchmarks/bench.py 10000 100000` and `dotnet run --project csharp/DTree.Tests -c Release -- bench 10000 100000`, trees of 100,000 nodes, both on the same Windows PC with Python 3.14.2 and .NET 9.0.21):

| shape | build time Python [s] | build time C# [s] | factor | renumberings Q1 / Q2, Python | renumberings Q1 / Q2, C# | positions moved per insertion, Python / C# |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 0.45 | 0.235 | 1.9× | 0 / 0 | 0 / 0 | 0 / 0 |
| chain | 0.25 | 0.189 | 1.3× | 0 / 0 | 0 / 0 | 0 / 0 |
| star (root) | 0.21 | 0.107 | 2.0× | 0 / 0 | 0 / 0 | 0 / 0 |
| star (inner node) | 0.37 | 0.127 | 2.9× | 0 / 0 | 0 / 0 | 0 / 0 |
| alternating (worst case) | 0.56 | 0.294 | 1.9× | 0 / 2,172 | 0 / 3,447 | 3.83 / 4.44 |

| query on a random tree of 100,000 nodes | Python | C# | factor |
| --- | ---: | ---: | ---: |
| `can_reach` / `CanReach`, per call | 1.4 µs | 0.37 µs | 3.8× |

Both implementations renumber identically except in the alternating worst case: C# stores positions as 64-bit numerator/denominator pairs and therefore renumbers somewhat earlier (denominators up to 2^40, renumbered regions use k/2^20) than Python with its unbounded integers (2^64 and k/2^32). The C# figures match those predicted by running the Python implementation with the C# limits. Building a tree is dominated by dictionary lookups on node names in both languages, so C# gains less there than on reachability queries, which compare positions directly.

## 1.1.0

Archived on Zenodo: doi:10.5281/zenodo.23397159.

**Rational positions in `DList`** (Python). Positions in Q1 and Q2 are now fractions. A new node gets the mediant (a+c)/(b+d) of its two neighbors, so inserting normally moves no other node. Rational positions were Enis Olgac's idea; the mediant construction, the fallback renumbering and the measurements were done with Claude (Anthropic).

Benchmark (`python benchmarks/bench.py 10000 100000`, trees of 100,000 nodes, same machine):

| shape | renumberings Q1 / Q2, 1.0.0 | renumberings Q1 / Q2, 1.1.0 | positions moved per insertion, 1.0.0 → 1.1.0 |
| --- | ---: | ---: | ---: |
| random | 0 / 0 | 0 / 0 | 0 → 0 |
| chain | 0 / 0 | 0 / 0 | 0 → 0 |
| star (root) | 0 / 13,764 | 0 / 0 | 5.53 → 0 |
| star (inner node) | 13,035 / 13,763 | 0 / 0 | 10.78 → 0 |
| alternating (worst case) | 0 / 13,072 | 0 / 2,172 | 5.84 → 3.83 |

Largest numerator or denominator at 100,000 nodes: 17–18 bits for chains and stars, 35 bits for random trees, 60 bits for the alternating worst case. `can_reach` costs about the same (2.5 → 2.7 µs per call; two multiplications instead of one integer comparison).

Other changes since 1.0.0:

- `DList.index(v)` returns a `Fraction` (SOURCE and SINK: −∞ and +∞).
- `python/benchmarks/bench.py`, with an alternating worst-case shape, and the counters `DList.renumber_count` and `DList.renumber_moved`.
- New tests: stars without renumbering, the alternating worst case, and 20,000 random list operations against a plain Python list.
- README: Zenodo DOIs, paper reference, background on positions.

## 1.0.0

First public release: Python implementation (insert, delete, delete_subtree, cut_n_paste, queries), C# prototype with WPF viewer, API reference. Archived on Zenodo: doi:10.5281/zenodo.23395711.
