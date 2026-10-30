# Triordinal—Topology and Structure of Directed Trees and Graphs: An Incremental Encoding

[![build](https://github.com/EnisOlgac/Triordinal/actions/workflows/build.yml/badge.svg)](https://github.com/EnisOlgac/Triordinal/actions/workflows/build.yml)
[![PyPI](https://img.shields.io/pypi/v/triordinal-dtree.svg)](https://pypi.org/project/triordinal-dtree/)
[![NuGet](https://img.shields.io/nuget/v/Triordinal.DTree.svg)](https://www.nuget.org/packages/Triordinal.DTree)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23760809.svg)](https://doi.org/10.5281/zenodo.23760809)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0009--7560--6107-a6ce39.svg)](https://orcid.org/0009-0009-7560-6107)

Triordinal encodes the topology of directed trees and graphs by linear orders. It is the new home of `DTree`, which until version 1.8.0 lived in [EnisOlgac/DTree](https://github.com/EnisOlgac/DTree) (PyPI `dtree-encoding`, NuGet `DTree.Encoding`); `DGraph`, the extension to directed graphs, will follow here as a separate package with its own license.

| Package | Python | NuGet | Depends on | License |
|---|---|---|---|---|
| DList: list with rational positions | `triordinal-dlist` (`triordinal.dlist`) | `Triordinal.DList` | nothing | MIT |
| DTree: directed trees, on two lists (`DTree`) or one (`EulerTree`) | `triordinal-dtree` (`triordinal.dtree`, `triordinal.dtree.euler`) | `Triordinal.DTree` | DList | MIT |
| DGraph: directed graphs (planned) | `triordinal-dgraph` (`triordinal.dgraph`) | `Triordinal.DGraph` | DList | to be decided |

DTree and DGraph do not depend on each other; both build on DList only.

`DTree` encodes the topology of a single-rooted directed tree explicitly by two linear projections, `Q1` and `Q2`. Reachability between any two nodes, as well as and/or queries over sets of nodes, is answered by comparing positions, without traversing the tree, and the encoding is updated incrementally as the tree changes.

## What Is New, in Short

- **For trees, the encoding itself is classical.** Whether *u* is an ancestor of *v* can be decided from pre- and post-order positions (Dietz, 1982), and such positions can be kept up to date under insertions (Dietz & Sleator, 1987; Bender et al., 2002), usually as an Euler tour: an open and a close position for each node in one list. DTree's `Q1` and `Q2` hold the same information: every node is a point in the plane `Q1` × `Q2`, and `Q2` is the post-order reversed. In the benchmarks, the Euler tour on one list is faster than DTree's two lists and needs less memory (see [Comparison with prior art](#comparison-with-prior-art)).
- **Constructed nodes for and/or queries**, an idea of the author (2021): a set of nodes is represented as a point of that plane (`VMin`, `VMax`, `UMin`, `UMax`), so "does *u* reach all of S?" is one comparison, "does *u* reach some of S?" a binary search, and both stay valid as the tree changes. They work on any encoding with two positions per node, the Euler tour included.
- **Rational positions**, also an idea of the author: a new position is the mediant of its neighbors, and a region is renumbered only when a denominator grows too large. Rational labels as such are known (floating-point intervals, Amagasa et al., 2003; nested intervals with Farey fractions, Tropashko, 2005). Against integer labels with the same renumbering rule, as in classical order maintenance, they avoid renumbering where new positions keep going into the same gap: appends at either end, nodes with many children, a gap filled from one side, where integer labels are relabeled every few dozen insertions. In time this does not pay off: in C#, integer labels are faster, because their relabeling is cheap and a comparison of integers costs half as much as one of fractions.
- **Why independent orders matter: graphs.** In a tree, the second order follows from the first: it is the post-order. In a directed graph it does not. Reachability in a graph needs two or three independent orders (its order dimension), and each order has a block structure of its own: the same vertex may have a different anchor in each Q. One list with an open and a close position per vertex holds a single structure of nested blocks, so it cannot represent them. DTree is the tree case of this; DGraph, planned here, maintains such orders for directed graphs incrementally, including graphs with cycles: a cycle is closed through a proxy of its head vertex, so the orders stay acyclic without collapsing strongly connected components into single vertices. For general directed graphs, no traversal produces such orders; DGraph has to construct them.

The reference implementation is in Python ([`python/`](python/)), with no dependencies and a test suite. The C# implementation and a WPF viewer are in [`csharp/`](csharp/).

## Projection Model

Each tree is encoded by two orderings of its nodes, both bracketed by the symbolic markers `[` (Source) and `]` (Sink):

- `Q1`—pre-order, children left to right
- `Q2`—pre-order, children right to left (sibling-reversed)

Node *u* can reach node *v* if and only if *u* strictly precedes *v* in both `Q1` and `Q2`. Reachability is irreflexive: no node reaches itself.

Inserting the edge (*u*, *v*) places *v* immediately after *u* in `Q2`, and at the end of *u*'s subtree in `Q1`. The end of a subtree is marked: a node with children has a *closing cell* in each list, directly after the last cell of its subtree, and a new child goes directly before its parent's closing cell. So no insertion, deletion or move has to search for the end of a subtree. Closing cells are not nodes; `Q1` and `Q2`, as the library shows them, list the nodes only.

## Background and Prior Art

`Q1` is the pre-order of a left-to-right depth-first traversal; `Q2` is the reversed post-order of the same traversal (equivalently, the pre-order with siblings right to left). That ancestry in a tree can be decided by comparing pre- and post-order positions is classical (Dietz, 1982). Maintaining positions in a list under insertions is the order-maintenance problem (Dietz & Sleator, 1987; Bender, Cole, Demaine, Farach-Colton & Zito, 2002); DTree uses rational positions instead (see below) and borrows the density rule of Bender et al. for its rare renumbering.

The insertion points of a new node are known in advance (see the [paper](#paper)): it becomes the last child of its parent in `Q1` (placed before the parent's delimiter, its closing cell) and the first child in `Q2` (placed directly after the parent). Every structural change is therefore local to both lists, and no traversal ever has to be recomputed. A summary of what is new compared to this prior art is at the top of this page.

- P. F. Dietz. Maintaining order in a linked list. *STOC 1982*, 122–127.
- P. F. Dietz, D. D. Sleator. Two algorithms for maintaining order in a list. *STOC 1987*, 365–372.
- M. A. Bender, R. Cole, E. D. Demaine, M. Farach-Colton, J. Zito. Two simplified algorithms for maintaining order in a list. *ESA 2002*, LNCS 2461, 152–164.
- T. Amagasa, M. Yoshikawa, S. Uemura. QRS: A robust numbering scheme for XML documents. *ICDE 2003*, 705–707.
- V. Tropashko. Nested intervals tree encoding in SQL. *ACM SIGMOD Record* 34(2), 2005, 47–52. doi:10.1145/1083784.1083793.

### Positions

Positions are fractions, an idea of the author. A new node gets the *mediant* (a+c)/(b+d) of its neighbors a/b and c/d (the Stern–Brocot construction), which always lies strictly between them, so inserting a node normally moves no other node. Repeated insertion into the same gap—a node with many children, or growth at either end of a list—keeps positions at O(log n) bits: 17 bits for a star of 100,000 children. Only insertions that alternate between the two halves of a gap make denominators grow (like Fibonacci numbers); when one grows too large, a small surrounding region is renumbered with simple fractions, larger regions being required to be sparser, as in Bender et al. A deep chain nests in the same way, each node into the gap between its parent and the parent's closing cell, and is renumbered locally at regular intervals of depth. See the benchmarks and the [changelog](CHANGELOG.md) for measurements.

The two implementations use different limits:

| | Python | C# |
|---|---|---|
| numbers | unbounded integers | 64-bit integers, compared with 128-bit products |
| renumbering when | a denominator would exceed 64 bits | a denominator would exceed 2⁴⁰, or a numerator 2⁶¹ |
| renumbered positions | k/2³² | k/2²⁰ |

## Comparison with Prior Art

The benchmarks (`python -m triordinal.dtree.bench --prior-art`, `-- bench prior-art`) compare DTree with the Euler tour on one list (same rational positions), with the Euler tour on integer labels, with pre/post numbers recomputed lazily before a query that follows a change, and with the parent walk of a classical tree. All answer the same queries, checked against each other; and/or queries use each encoding's own constructed points. Results: [`docs/prior-art.md`](docs/prior-art.md).

## Key Features

- Two encodings of a tree with the same API: `DTree` on two lists, `Q1` and `Q2`, and `EulerTree` on one list (`Q1` with its closing cells, the Euler tour), which is faster and smaller for trees
- Rational positions (the default) or integer positions (`positions="integer"`), the user's choice
- Single-rooted directed tree; no aliasing, no duplicate nodes
- Reachability check in O(1) via positions in `Q1` and `Q2`
- Insertion in O(1): the end of every subtree is marked by a closing cell (plus the occasional local renumbering)
- Dynamic operations: `insert`, `delete` (children move up), `delete_subtree`, `cut_n_paste` (move a subtree)
- Structural queries: ancestry, depth, paths, subtrees
- And/or queries on the topology in O(1) or O(log k) via constructed nodes VMin, VMax, UMin and UMax (see below)
- No limit on tree depth or width

## And/or Queries on the Topology

Does *u* reach all of a set of nodes *S* (*u* → *s*₁ **and** *u* → *s*₂ …), or some of them (**or**)? Is *v* reached by all of *S*, or by some? Each of these questions reduces to comparisons with a *constructed node*, an idea of the author (E. Olgac, "Topology and Structure of Directed Graphs - Inducing a Subgraph," 2021): the minimum or the maximum of each index over *S*, taken separately in `Q1` and `Q2`. The two values usually come from two different members, so the constructed node is no real node, but it is compared like one. Its name says which role *S* plays in `can_reach(u, v)`: *V* when *S* is the target, *U* when *S* is the source.

| question | constructed node | test | exact? |
| --- | --- | --- | --- |
| *u* reaches all of *S* | VMin | *u* left of VMin in both lists | yes, O(1) |
| *u* reaches some of *S* | VMax | *u* left of VMax in both lists | necessary only; exact in O(log k) |
| all of *S* reach *v* | UMax | *v* right of UMax in both lists | yes, O(1) |
| some of *S* reach *v* | UMin | *v* right of UMin in both lists | necessary only; exact in O(log k) |

For the two "some" questions the constructed node only rejects quickly. The exact answers use the order of the members in `Q1`: the subtree of *u* is the block directly after *u* in `Q1`, so *u* reaches some member exactly when the first member after *u* does; and *v* is reached by some member exactly when the last *topmost* member before *v* (one with no ancestor in *S*) reaches it.

```python
# the Quick Start tree (A -> B -> C, A -> D)
t.vmin(["C", "D"]).reaches_all("A")        # True: A reaches C and D
t.vmin(["C", "D"]).reaches_all("B")        # False: B reaches C only
t.vmax(["C", "D"]).reaches_some("B")       # True
t.umax(["A", "B"]).reached_by_all("C")     # True: A and B both reach C
t.umin(["B", "D"]).reached_by_some("C")    # True: B reaches C
```

In C#: `t.VMin(nodes).ReachesAll(u)`, `t.VMax(nodes).ReachesSome(u)`, `t.UMax(nodes).ReachedByAll(v)`, `t.UMin(nodes).ReachedBySome(v)`, with names or node handles; `MayReachSome` and `MayBeReachedBySome` are the O(1) filters. A constructed node stores its members, not positions; since insertions keep the order of existing nodes, it stays valid while the tree grows, and after a deletion or a move it is recomputed on its next use. A classical tree with parent and child links answers the same questions by climbing towards the root. See [`docs/and-or-queries.md`](docs/and-or-queries.md).

## Use Cases

`DTree` fits wherever a hierarchy changes while it is being queried:

- **Tree views with expand/collapse.** A collapsed node shows only its own row; an expanded one shows its children. `Q1` is already the display order, so the visible rows follow by walking `Q1` and jumping over the block of every collapsed node with `subtree_last`. Whether a node is visible is an and/or query: it is hidden exactly when some collapsed node reaches it.

  ```python
  def visible_rows(t, collapsed):
      rows, v = [], t.root
      while v is not None:
          rows.append(v)
          if v in collapsed:
              v = t.subtree_last(v)      # jump over the hidden block
          v = t.next_in_q1(v)            # Q1 is the display order
      return rows

  collapsed = t.umin(["B"])               # the collapsed nodes, kept as a constructed node
  collapsed.add("D")                      # collapse D
  collapsed.discard("B")                  # expand B
  hidden = collapsed.reached_by_some("C") # is C inside a collapsed subtree?
  row = collapsed.covering("C") or "C"    # the visible row that contains C
  ```

  The constructed node also answers `v in collapsed`, so it can be passed to `visible_rows` directly.

  The benchmarks include this use case against a classical tree model with parent, child and sibling links. The classical model wins on shallow trees and loses as the depth grows; see [the parent walk's home ground](docs/parent-walk.md).

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
t.insert("A", "B")
t.insert("B", "C")

t.can_reach("A", "C")   # True
t.path_to_root("C")     # ['C', 'B', 'A']
t.q1, t.q2              # (['A', 'B', 'C'], ['A', 'B', 'C'])

# Node handles skip the lookup by name (insert returns the new node's handle):
a, c = t.get_node("A"), t.get_node("C")
t.can_reach(a, c)       # True, two position comparisons
d = t.insert(a, "D")
```

The same tree on one list, the Euler tour (faster and smaller for trees; no `Q2`):

```python
from triordinal.dtree.euler import EulerTree

e = EulerTree("E1")                      # positions="integer" for integer positions
e.insert("A", "B")
e.can_reach("A", "B")   # True
```

Load a sample tree (`parent: child1; child2` per line):

```python
t = DTree.from_file("examples/Test.csx")
```

See [`python/README.md`](python/README.md) for the full API and semantics. Run the tests with:

```
cd python
python -m unittest discover -s tests
```

## C# Implementation

[`csharp/Triordinal.DTree/`](csharp/Triordinal.DTree/) (with the list in [`csharp/Triordinal.DList/`](csharp/Triordinal.DList/)) is a C# (.NET 9) port of the Python implementation with the same API in C# naming: `Insert`, `Delete`, `DeleteSubtree`, `CutNPaste`, `CanReach`, `PathToRoot`, `Depth`, …, and `Q1`/`Q2` as read-only views (`Projection`) of the two lists with rational positions. Its test program checks every query against a brute-force model, as the Python tests do:

```
dotnet run --project csharp/Triordinal.DTree.Tests -c Release            # tests
dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench   # benchmarks
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
t.CanReach(a, c);       // true, two position comparisons
DNode d = t.Insert(a, "D");
```

[`csharp/Tree.View/`](csharp/Tree.View/) is a WPF viewer (Windows only) built on `Triordinal.DTree`: *Select DiTree* opens a `.csx` file from [`examples/`](examples/), lists the inserted edges, and draws the tree once along `Q1` and once along `Q2`. Open `csharp/Triordinal.sln` in Visual Studio and start `Tree.View`.

## Original C# Prototype

The author's original C# prototype (with the WPF viewer on top of it) is included in the releases up to version 1.1.0 and archived on Zenodo (version 1.1.0: [10.5281/zenodo.23397159](https://doi.org/10.5281/zenodo.23397159)). It was removed from the repository afterwards; `DTree.Core` (now `Triordinal.DTree`) replaces it.

## Documentation

- [API reference (Markdown)](docs/API.md)
- [And/or queries on the topology](docs/and-or-queries.md)—constructed nodes, with a comparison to classical doubly linked trees and measurements
- [The parent walk's home ground](docs/parent-walk.md)—where a classical parent walk is enough, where it is not, and a tree-view use case
- [API reference (PDF)](docs/User.Doc.pdf)—LaTeX source: [`docs/User.Doc.tex`](docs/User.Doc.tex)

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

The Python implementation was written with Claude (Anthropic) from the C# prototype and the API reference.
