# Triordinal—Topology and Structure of Directed Trees and Graphs: An Incremental Encoding

[![build](https://github.com/EnisOlgac/Triordinal/actions/workflows/build.yml/badge.svg)](https://github.com/EnisOlgac/Triordinal/actions/workflows/build.yml)
[![PyPI](https://img.shields.io/pypi/v/triordinal-dtree.svg)](https://pypi.org/project/triordinal-dtree/)
[![NuGet](https://img.shields.io/nuget/v/Triordinal.DTree.svg)](https://www.nuget.org/packages/Triordinal.DTree)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23760809.svg)](https://doi.org/10.5281/zenodo.23760809)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0009--7560--6107-a6ce39.svg)](https://orcid.org/0009-0009-7560-6107)

Triordinal encodes the topology of directed trees and graphs by linear orders. It is the new home of `DTree`, which until version 1.8.0 lived in [EnisOlgac/DTree](https://github.com/EnisOlgac/DTree) (PyPI `dtree-encoding`, NuGet `DTree.Encoding`).

| Package | Python | NuGet | Depends on | License |
|---|---|---|---|---|
| DList: list with rational positions | `triordinal-dlist` (`triordinal.dlist`) | `Triordinal.DList` | nothing | MIT |
| DTree: directed trees | `triordinal-dtree` (`triordinal.dtree`) | `Triordinal.DTree` | DList | MIT |
| DGraph: directed graphs (planned) | `triordinal-dgraph` (`triordinal.dgraph`) | `Triordinal.DGraph` | DList | to be decided |

DTree and DGraph do not depend on each other; both build on DList only.

**DTree 3.0** keeps one projection, `Q1`, and the structure of the tree in its vertices. A vertex knows its parent, its kids (one list, read left to right from one end and right to left from the other), its place in its parent's kids list, and its cell in `Q1`. There is no second projection and there are no closing cells. Reachability is decided by comparing positions in `Q1`, with the end of a block read from the sibling structure; see [Structure](#structure). The design is the author's (November 2026).

DTree 3.0 is not compatible with 2.x: its API was redrawn for the new structure (see the [changelog](CHANGELOG.md)). The earlier encodings remain in the package for comparison, with their own API:

- **DTree 2.x** on two projections, `Q1` and `Q2`: `triordinal.dtree.two_lists.DTree` (C# `DirectedTrees.TwoLists.DTree`).
- **EulerTree** on one projection with closing cells, the Euler tour: `triordinal.dtree.euler.EulerTree` (C# `Triordinal.DTree.Euler.EulerTree`).

**`DGraph`**, planned here as a separate package with its own license, will encode directed graphs, inserted edge by edge. In a graph the second order no longer follows from the first, so DGraph needs independent projections, `Q1` and `Q2`, and eventually a third, `Q3`.

## What Is New, in Short

- **The structure lives in the vertices, the order in one projection.** `Q1` is the pre-order of the tree. The block of a vertex in `Q1` runs from its own cell to its *delimiter*: its right sibling, or, if it is the last kid, its parent's delimiter. In Prolog terms the block is a difference list whose tail is the delimiter. Nothing marks the end of a block; the sibling structure says where it is.
- **Reachability is decided locally, as a cascade.** *u* reaches *v* exactly when *v* lies after *u* and before *u*'s delimiter. Almost every query is settled by the first steps, without looking for the delimiter: *v* is not after *u*; *u* has no kids; *u* has a right sibling; *u*'s last kid is a leaf. In random and reading-order trees only 2 to 3 queries in 100 go further, and those take one or two steps on average.
- **Sequences are crossed in one step.** A sequence of only kids, a list standing upright inside the tree, is treated as one unit (*vertical run*): its members share an object that knows the run's top. A run is cut where a vertex gets a second kid and joined where a vertex is left with one; only the shorter part is renumbered, so a cut near either end of a long run is cheap. The idea of handling a sequence as one vertex until it branches comes from the author's earlier work on control-flow analysis. A tree that is nothing but a sequence is a list; use `DList` for it.
- **Lighter and faster to update, as fast to query.** In C#, on 100,000 nodes, DTree 3.0 builds a tree 1.1 to 6 times faster than DTree 2.x and EulerTree, answers queries as fast (60 to 90 ns), moves subtrees twice as fast as DTree 2.x, and needs about 280 bytes per node against 380 to 460 for EulerTree and 520 to 630 for DTree 2.x (see [Comparison with prior art](#comparison-with-prior-art)).
- **Constructed nodes for and/or queries**, an idea of the author (2021): a set of nodes is reduced to what a query needs, so "does *u* reach all of S?" is two comparisons and "does *u* reach some of S?" a binary search. In 3.0 they are built for the query at hand.
- **Rational positions**, developed independently by the author: a new position is the mediant of its neighbors, and a region is renumbered only when a new position can no longer be stored (see [Positions](#positions)).
- **For trees, deciding ancestry by positions is classical** (Dietz, 1982), and so is keeping positions up to date under insertions (Dietz & Sleator, 1987; Bender et al., 2002). DTree 2.x stored the second order as a list (`Q2`), the Euler tour stores the end of every block as a closing cell; DTree 3.0 stores neither and reads the end of a block from the sibling structure. How one list and two lists differ: [One list and two lists](docs/one-and-two-lists.md).

The reference implementation is in Python ([`python/`](python/)), with no dependencies and a test suite. The C# implementation and a WPF viewer are in [`csharp/`](csharp/).

## Structure

A vertex keeps four things:

- its **parent**;
- its **kids list**, a property of the vertex: read from one end it is left to right (LR), from the other right to left (RL);
- its **handle** in its parent's kids list, the cell that represents it there, so its siblings are one step away;
- its **cell in `Q1`**, the pre-order with kids left to right, bracketed by the markers `[` (Source) and `]` (Sink).

The block of *u* in `Q1` runs from its own cell to just before its delimiter: its right sibling, or, when it is the last kid, the delimiter of its parent (SINK above the root). Node *u* reaches node *v* if and only if

> cell(*u*) < cell(*v*) < cell(delimiter(*u*)).

Reachability is irreflexive: no node reaches itself. `can_reach` decides it as a cascade of local steps:

1. *v* is not right of *u* in `Q1`: no.
2. *u* has no kids: no.
3. *u* has a right sibling (or is the root): compare *v* with it.
4. *u*'s last kid: *v* up to it is reached; if it is a leaf, its next cell in `Q1` is *u*'s delimiter.
5. Otherwise find the delimiter, up through the ancestors that are last kids; a vertical run is crossed in one step.

A new kid goes into `Q1` directly after its parent when it is the first kid, directly before its right sibling when it has one, and before its parent's delimiter when it is appended as the last kid; only the last case looks for the delimiter. A move cuts the block of a subtree from `Q1` and pastes it at its new place; in the tree, only the parent changes.

## Background and Prior Art

`Q1` is the pre-order of a left-to-right depth-first traversal. That ancestry in a tree can be decided by comparing pre- and post-order positions is classical (Dietz, 1982); the plane they span is the pre/post plane of the XPath Accelerator (Grust, 2002), in which the staircase join (Grust, van Keulen & Teubner, 2003) evaluates queries over sets of context nodes, pruning a set to its topmost members as `UMin` does. Maintaining positions in a list under insertions is the order-maintenance problem (Dietz & Sleator, 1987; Bender, Cole, Demaine, Farach-Colton & Zito, 2002); DTree uses rational positions instead (see below) and borrows the density rule of Bender et al. for its rare renumbering.

The usual encodings store the end of every block: as a post-order number, as a second list (DTree 2.x's `Q2`), or as a closing position (the Euler tour). DTree 3.0 stores no end; the end of a block is the next sibling's cell, found from the vertices. The insertion points of a new node are known in advance (see the [paper](#paper)), so every structural change is local, and no traversal ever has to be recomputed.

- P. F. Dietz. Maintaining order in a linked list. *STOC 1982*, 122–127.
- P. F. Dietz, D. D. Sleator. Two algorithms for maintaining order in a list. *STOC 1987*, 365–372.
- M. A. Bender, R. Cole, E. D. Demaine, M. Farach-Colton, J. Zito. Two simplified algorithms for maintaining order in a list. *ESA 2002*, LNCS 2461, 152–164.
- T. Amagasa, M. Yoshikawa, S. Uemura. QRS: A robust numbering scheme for XML documents. *ICDE 2003*, 705–707.
- V. Tropashko. Nested intervals tree encoding in SQL. *ACM SIGMOD Record* 34(2), 2005, 47–52. doi:10.1145/1083784.1083793.
- T. Grust. Accelerating XPath location steps. *SIGMOD 2002*, 109–120.
- T. Grust, M. van Keulen, J. Teubner. Staircase join: teach a relational DBMS to watch its (axis) steps. *VLDB 2003*, 524–535. doi:10.1016/B978-012722442-8/50053-7.

### Positions

Positions are fractions, developed independently by the author. A new node gets the *mediant* (a+c)/(b+d) of its neighbors a/b and c/d (the Stern–Brocot construction), which always lies strictly between them, so inserting a node normally moves no other node. Repeated insertion into the same gap—a node with many children, or growth at either end of a list—keeps positions at O(log n) bits: 17 bits for a star of 100,000 children. Only insertions that alternate between the two halves of a gap make denominators grow (like Fibonacci numbers); only when a new position can no longer be stored is a small surrounding region renumbered with simple fractions, larger regions being required to be sparser, as in Bender et al. Rational labels as such are known (floating-point intervals, Amagasa et al., 2003; nested intervals with Farey fractions, Tropashko, 2005).

Both implementations use the same bounds, those of C#'s 64-bit numbers (compared with 128-bit products): a region is renumbered when a new position's denominator, or the size of its numerator, would exceed 2⁶¹, and renumbered positions are fractions k/2²⁰. Python's unbounded integers would not need the bound; it keeps it so that both languages renumber at the same moments and give the same positions.

Moving a subtree (`cut_n_paste`) places its block as one piece. With integer positions the block is shifted as a whole, keeping its spacing, when its span fits into the gap at its new place, and otherwise spread evenly over the gap; with rational positions its cells get the mediants that linking them one after another would give, checked at once. Only a block that does not fit renumbers a region around it.

Integer positions are the alternative, chosen per tree (`DTree(..., positions="integer")`; in C# `Positions.Integer`) or per list (`DList(name, positions="integer")`). A position is then an integer label in [0, 2⁶²], as in classical order maintenance: a new position is the midpoint of its neighbors' labels, and when no integer is left between them, the smallest surrounding region with enough room is relabeled evenly, with the same density rule as for fractions. Appends at either end and nodes with many children are then relabeled every few dozen insertions, which fractions avoid; in return, two integer positions are compared directly, without the multiplications that fractions need. Measurements of both kinds (on the lists of DTree 2.x and EulerTree): [`docs/prior-art.md`](docs/prior-art.md).

## Comparison with Prior Art

The benchmark of DTree 3.0 (`python -m triordinal.dtree.bench3`; C# `-- bench3`) compares it with DTree 2.x and EulerTree on the same operations, all through node handles. C#, .NET 9, 100,000 nodes, measured by the author on an Intel NUC:

| | DTree 2.x | EulerTree | DTree 3.0 |
|---|---:|---:|---:|
| build, µs per insertion: random / chain / star / reading order | 1.64 / 2.80 / 0.93 / 1.14 | 0.91 / 1.65 / 0.60 / 0.81 | 0.81 / 0.46 / 0.37 / 0.66 |
| query, µs: same shapes | 0.060 / 0.086 / 0.074 / 0.083 | 0.060 / 0.078 / 0.071 / 0.071 | 0.059 / 0.089 / 0.060 / 0.067 |
| chain of 20,000 grown at the bottom, a child near the top (µs per round) | 3.45 | 3.14 | 1.81 |
| chain of 20,000, kids appended under its middle node (µs per insertion) | 0.19 | 0.13 | 0.55 |
| random move plus a query (µs) | 8.58 | 3.77 | 4.01 |
| memory, bytes per node: random / chain | 523 / 630 | 383 / 458 | 285 / 279 |

The one row where DTree 3.0 is behind is the worst case of its vertical runs: the first kid under the middle of a chain cuts the run exactly in half, and 10,000 vertices get a new run object once. A cut never costs more than half a run.

The earlier benchmarks (`python -m triordinal.dtree.bench`, `-- bench`) compare DTree 2.x and EulerTree with the Euler tour on one list with rational, integer, double and decimal positions, with pre/post numbers recomputed lazily, and with the parent walk of a classical tree. Results: [`docs/prior-art.md`](docs/prior-art.md).

## Key Features

- One projection, `Q1`, and the structure in the vertices: parent, kids list, handle, cell
- Reachability by comparing positions, decided locally in almost every case; a sequence of only kids is crossed in one step
- Insertion as first kid, last kid, or before or after a sibling; the end of a block is read from the siblings, not stored
- Dynamic operations: `insert`, `insert_first`, `insert_before`, `insert_after`, `delete` (kids move up), `delete_subtree`, `cut_n_paste` (move a subtree)
- Structural queries: parent, children, ancestry, depth, path to the root, subtree
- And/or queries on the topology with constructed nodes VMin, VMax, UMin and UMax, built for the query at hand (see below)
- Rational positions (the default) or integer positions (`positions="integer"`)
- Single-rooted directed tree; no duplicate nodes; no limit on depth or width

## And/or Queries on the Topology

Does *u* reach all of a set of nodes *S* (*u* → *s*₁ **and** *u* → *s*₂ …), or some of them (**or**)? Is *v* reached by all of *S*, or by some? Each of these questions reduces to comparisons with a *constructed node*, an idea of the author (E. Olgac, "Topology and Structure of Directed Graphs - Inducing a Subgraph," 2021). Its name says which role *S* plays in `can_reach(u, v)`: *V* when *S* is the target, *U* when *S* is the source. In DTree 3.0 a constructed node is built for the query at hand: it sorts the members by their position in `Q1` and, where the question needs them, finds their delimiters. After the tree changes, build it again.

| question | constructed node | test | cost per query |
| --- | --- | --- | --- |
| *u* reaches all of *S* | VMin | *u* lies before the first member, *u*'s delimiter after the last | O(1) |
| *u* reaches some of *S* | VMax | the first member after *u* lies before *u*'s delimiter | O(log k) |
| all of *S* reach *v* | UMax | *v* lies after the last member and before the first members' delimiter | O(1) |
| some of *S* reach *v* | UMin | the last *topmost* member before *v* (one with no ancestor in *S*) contains *v* | O(log k) |

Building costs O(k log k) for the sort, plus a delimiter per member for UMax and UMin. A constructed node pays off when several *u* or *v* are asked against the same *S*; a single question is k reachability queries. See [`docs/and-or-queries.md`](docs/and-or-queries.md) (written for DTree 2.x).

```python
# the Quick Start tree (A -> B -> C, A -> D)
t.vmin(["C", "D"]).reaches_all("A")        # True: A reaches C and D
t.vmin(["C", "D"]).reaches_all("B")        # False: B reaches C only
t.vmax(["C", "D"]).reaches_some("B")       # True
t.umax(["A", "B"]).reached_by_all("C")     # True: A and B both reach C
t.umin(["B", "D"]).reached_by_some("C")    # True: B reaches C
```

In C#: `t.VMin(nodes).ReachesAll(u)`, `t.VMax(nodes).ReachesSome(u)`, `t.UMax(nodes).ReachedByAll(v)`, `t.UMin(nodes).ReachedBySome(v)` and `t.UMin(nodes).Covering(v)`, with names or node handles.

## Use Cases

Wherever a hierarchy changes while it is being queried:

- **Tree views with expand/collapse.** `Q1` is the display order. The visible rows are those not reached by any collapsed node: `umin(collapsed).reached_by_some(v)`, and `covering(v)` gives the collapsed row that hides *v*.
- **File and directory trees:** is this file under that folder, while files are added and moved?
- **Syntax trees and scopes** in editors and compilers: is this node inside that function, during editing?
- **Hierarchies** such as category trees, org charts, nested comments or UI component trees.
- **XML/JSON documents:** does this element contain all (and) or any (or) of these elements?

## Installation

```
pip install triordinal-dtree          # Python, imported as triordinal.dtree
dotnet add package Triordinal.DTree   # C#, namespace DirectedTrees (DList: namespace Triordinal)
```

To be notified of new versions on GitHub, use *Watch → Custom → Releases*.

## Quick Start (Python)

```python
from triordinal.dtree import DTree   # pip install triordinal-dtree

t = DTree("P1")
t.insert("A", "B")      # the first insert makes A the root
t.insert("B", "C")
t.insert("A", "D")      # D becomes A's last kid

t.can_reach("A", "C")   # True
t.can_reach("B", "D")   # False
t.path_to_root("C")     # ['C', 'B', 'A']
t.q1                    # ['A', 'B', 'C', 'D']

# Node handles skip the lookup by name (every insert returns the new node's handle):
a, c = t.get_node("A"), t.get_node("C")
t.can_reach(a, c)       # True
e = t.insert_first(a, "E")   # E becomes A's first kid: directly after A in Q1
```

Load a sample tree (`parent: child1; child2` per line; `s > c` and `s < c` insert after or before a sibling):

```python
t = DTree.from_file("examples/Test.csx")
```

The earlier encodings, for comparison:

```python
from triordinal.dtree.two_lists import DTree as DTree2   # DTree 2.x, Q1 and Q2
from triordinal.dtree.euler import EulerTree              # one list with closing cells
```

See [`python/dtree/README.md`](python/dtree/README.md) for the API. Run the tests with:

```
cd python/dtree
python -m unittest discover -s tests
```

## C# Implementation

[`csharp/Triordinal.DTree/`](csharp/Triordinal.DTree/) (with the list in [`csharp/Triordinal.DList/`](csharp/Triordinal.DList/)) is a C# (.NET 9) port of the Python implementation with the same API in C# naming: `Insert`, `InsertFirst`, `InsertBefore`, `InsertAfter`, `Delete`, `DeleteSubtree`, `CutNPaste`, `CanReach`, `PathToRoot`, `Depth`, `Subtree`, `Q1`, …. Its test program checks every query against a brute-force model, as the Python tests do:

```
dotnet run --project csharp/Triordinal.DTree.Tests -c Release             # tests
dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench3   # DTree 3.0 against 2.x and EulerTree
dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench    # the earlier benchmarks
```

```csharp
using DirectedTrees;

var t = new DTree("P1");
t.Insert("A", "B");
t.Insert("B", "C");
t.CanReach("A", "C");   // true
t.PathToRoot("C");      // ["C", "B", "A"]

// Node handles skip the lookup by name:
DNode a = t.GetNode("A"), c = t.GetNode("C");
t.CanReach(a, c);       // true
DNode d = t.Insert(a, "D");
```

DTree 2.x is `DirectedTrees.TwoLists.DTree`, EulerTree `Triordinal.DTree.Euler.EulerTree`, both in the same package.

[`csharp/Tree.View/`](csharp/Tree.View/) is a WPF viewer (Windows only): *Select DiTree* opens a `.csx` file from [`examples/`](examples/), lists the inserted edges, and draws the tree once along `Q1` and once along `Q2`. It is built on DTree 2.x, which keeps both lists. Open `csharp/Triordinal.sln` in Visual Studio and start `Tree.View`.

## Original C# Prototype

The author's original C# prototype (with the WPF viewer on top of it) is included in the releases up to version 1.1.0 and archived on Zenodo (version 1.1.0: [10.5281/zenodo.23397159](https://doi.org/10.5281/zenodo.23397159)). It was removed from the repository afterwards; `DTree.Core` (now `Triordinal.DTree`) replaces it.

## Documentation

- [API reference (Markdown)](docs/API.md)
- [One list and two lists](docs/one-and-two-lists.md)—containment and topology, where the next branch begins, navigated traversal; the way to DTree 3.0
- [And/or queries on the topology](docs/and-or-queries.md)—constructed nodes, with a comparison to classical doubly linked trees and measurements (DTree 2.x)
- [The parent walk's home ground](docs/parent-walk.md)—where a classical parent walk is enough, where it is not, and a tree-view use case (DTree 2.x)
- [API reference of DTree 2.0 (PDF)](docs/User.Doc.pdf)—LaTeX source: [`docs/User.Doc.tex`](docs/User.Doc.tex)

## Repository Layout

```
Triordinal/
├── python/         Python packages: dlist/ (triordinal-dlist), dtree/ (triordinal-dtree)
├── csharp/         C# implementation (Triordinal.DList, Triordinal.DTree, Triordinal.DTree.Tests) and WPF viewer
│                   (Tree.View)
├── examples/       sample trees (.csx: "parent: child1; child2")
├── docs/           API reference (Markdown, PDF, LaTeX sources)
├── CITATION.cff    citation metadata
├── LICENSE.md      MIT License
└── README.md
```

## Paper

The method is described in:

> E. Olgac, "Topology and Structure of Directed Trees: An Incremental Encoding," *Artificial Intelligence*. IntechOpen, Dec. 11, 2025. doi: [10.5772/intechopen.1013408](https://doi.org/10.5772/intechopen.1013408).

## Citing

If you use `DTree` in academic work, please cite the paper above. GitHub's "Cite this repository" button in the sidebar shows it, using the metadata in [`CITATION.cff`](CITATION.cff).

To cite the software itself, use its Zenodo archive: E. Olgac, *Triordinal—Topology and Structure of Directed Trees and Graphs: An Incremental Encoding*, Zenodo, 2026. doi: [10.5281/zenodo.23760809](https://doi.org/10.5281/zenodo.23760809). Versions up to 1.8.0, as DTree: E. Olgac, *DTree—Topology and Structure of Directed Trees: An Incremental Encoding*, version 1.8.0, Zenodo, 2026. doi: [10.5281/zenodo.23685810](https://doi.org/10.5281/zenodo.23685810) (all versions: [10.5281/zenodo.23395710](https://doi.org/10.5281/zenodo.23395710)).

## Acknowledgements

Thanks to Onur Safi for a careful review of DTree 1.8.0, which led to the fixes and changes in Triordinal 2.0.0 and 2.1.0, and to Sinan Emiroğlu for his feedback, in particular on the package name clash and on stating the contribution of DTree more concisely.

## License

DList and DTree are released under the MIT License. See [`LICENSE.md`](LICENSE.md) for details.

## Author

Enis Olgac · [ORCID 0009-0009-7560-6107](https://orcid.org/0009-0009-7560-6107) · [github.com/EnisOlgac](https://github.com/EnisOlgac) · enis@digraphs.info

The Python implementation was written with Claude (Anthropic) from the C# prototype and the API reference. DTree 3.0's structure was designed by the author and implemented with Claude, in Python and C#.
