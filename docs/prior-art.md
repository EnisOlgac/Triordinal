# Comparison with Prior Art

The benchmarks compare DTree with classical encodings of ancestry, implemented as fairly as DTree itself (`python/dtree/triordinal/dtree/prior_art.py`, ported to C# in `csharp/Triordinal.DTree.Tests/PriorArt.cs`):

- **Euler tour, rational:** the parenthesis encoding on one list. Every node has an open and a close cell; *u* is an ancestor of *v* exactly when *v*'s open cell lies between *u*'s open and close cells (Dietz, 1982). The list is the same `DList` with rational positions that DTree uses, so the only difference to DTree is one list instead of two. It keeps no parent or child links (DTree does, for parent queries, sibling insertion, deletion and moves), so its insertions do less bookkeeping.
- **Euler tour, double and decimal:** the same tour on floating-point positions. Next to SOURCE or SINK a new position is one unit beyond its neighbor, as with rational positions; between two cells, a double gets the midpoint, and a decimal the left neighbor plus half the gap rounded at its most significant digit, as in the original `List.cs` of DTree 1.0.0 (Enis Olgac's prototype, which used C#'s `decimal`). When no representable position is left, a region is respaced evenly with the same density rule. Python's reference uses `float` and `Decimal` limited to 28 significant digits and 28 decimal places, as C#'s `decimal`.
- **Euler tour, integer:** the same tour on integer labels, as in classical order maintenance (Dietz & Sleator, 1987; Bender et al., 2002): a new cell gets the midpoint of its neighbors' labels in [0, 2⁶²]; when no integer is left between them, the smallest surrounding region with enough room is relabeled evenly, with the same density rule as `DList`. Compared with the rational tour, only the kind of position differs.
- **Pre/post numbers, lazy:** pre- and post-order numbers from a traversal, recomputed only before a query that follows a change.
- **Parent walk:** a classical tree with parent links; *u* reaches *v* if *u* is met on the way from *v* to the root.

All contenders answer the same queries, and the benchmarks check that their answers agree. And/or queries use each encoding's own constructed points: DTree's `VMin`, `VMax`, `UMin`, `UMax`; for the Euler tour the minimum and maximum open and close positions over the set; for pre/post numbers the same over the numbers.

Run them with `python -m triordinal.dtree.bench --prior-art` or `dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench prior-art`.

## What the measurements show

- **One list against two.** For trees, Q1 and Q2 hold the same information as an Euler tour: `Q2` is the post-order reversed. The Euler tour maintains it in one list, with half the insertions, and is faster than DTree for insertions and queries and needs less memory. The constructed points carry over unchanged.
- **Floating-point positions** behave like rational ones at the ends of a list (one unit outward, no renumbering), but run out of digits inside it. The decimal's wider precision (96 bits against 53) saves most respacing in random trees and stars; in time, `decimal` is the slowest kind, since its arithmetic and comparisons run in software. Rounding the half gap at its most significant digit, as the original `List.cs` did, saves respacing for decimals where a gap is filled from alternating sides (in C#, 29,040 instead of 46,158 renumberings for the alternating tree of 100,000 nodes) and a little in the top-down comb (5,679 instead of 6,632); for chains, stars and a single gap filled from alternating sides it costs a little, and it makes insertions slower (the rounding takes a logarithm and divisions). For doubles it helps only in the comb, in base 2; for integer labels it gives nothing, since integers have no relative precision to save. Python's `Decimal`, though limited to C#'s digits, does not round exactly like C#'s `decimal`, so its counts for the decimal variants differ; the C# counts are the ones that hold for `decimal`.
- **Rational against integer positions.** Rational positions renumber least in every pattern: they avoid renumbering where new positions keep going into the same gap (appends at either end, nodes with many children, a gap filled from one side), where integer labels are relabeled every few dozen insertions. In time this does not pay off: in C#, a query on integers or doubles takes 0.035 µs against 0.054 µs on rationals (one comparison of two numbers instead of two 128-bit products), and integer labels are the fastest kind for insertions with queries at every depth from 1,000 on. Relabeling an integer region is cheap, and in total about as many positions move as with rationals.
- **Pre/post numbers** win when queries come in large batches, and for queries on a tree that no longer changes; they lose badly when insertions and queries alternate.
- **The parent walk** wins on shallow trees (depth 10 to 1,000 in C#) and loses as the depth grows: 67 µs per step at depth 100,000, against 1.5 µs for the Euler tour and 3.5 µs for DTree.

## DTree and EulerTree

From these results, Triordinal 2.2.0 offers the Euler tour next to DTree: `EulerTree` (`triordinal.dtree.euler`, C# `Triordinal.DTree.Euler`) keeps DTree's Q1 alone, with its closing cells, and has DTree's API except Q2. Both take rational positions (the default) or integer positions. Unlike the contender above, an EulerTree keeps parent and child links and needs no closing cell for a leaf. The benchmark section "DTree and EulerTree" (`--euler`, `-- bench euler`) compares the four combinations.

Python 3.13, Claude's Linux workspace (Oct 30, 2026), 100,000 nodes:

| | DTree, rational | DTree, integer | EulerTree, rational | EulerTree, integer |
| --- | ---: | ---: | ---: | ---: |
| insert + query, depth 10,000 [µs] | 5.59 | 4.56 | 2.96 | 3.02 |
| single query [µs] | 0.607 | 0.505 | 0.442 | 0.430 |
| reaches some, set of 1,000 [µs] | 2.555 | 2.270 | 2.288 | 2.158 |
| renumberings, chain (summed over the lists) | 8,692 | 44,562 | 4,346 | 22,281 |
| renumberings, star (root) | 0 | 21,723 | 0 | 10,277 |
| memory [bytes per node] | 801 | 729 | 547 | 510 |

C#, .NET 9, measured by Enis Olgac on his NUC (Oct 30, 2026, `-- bench euler`; full report in [`benchmarks/csharp/2026-10-30_10-26.md`](../benchmarks/csharp/2026-10-30_10-26.md)), 100,000 nodes:

| | DTree, rational | DTree, integer | EulerTree, rational | EulerTree, integer |
| --- | ---: | ---: | ---: | ---: |
| insert + query, depth 10 [µs] | 1.158 | 1.449 | 0.838 | 0.792 |
| insert + query, depth 100,000 [µs] | 3.088 | 2.254 | 1.860 | 1.127 |
| single query [µs] | 0.051 | 0.033 | 0.045 | 0.033 |
| reaches all, set of 1,000 [µs] | 0.039 | 0.036 | 0.062 | 0.020 |
| reaches some, set of 1,000 [µs] | 0.248 | 0.248 | 0.230 | 0.176 |
| renumberings, chain (summed over the lists) | 13,790 | 44,562 | 6,895 | 22,281 |
| renumberings, star (root) | 0 | 21,723 | 0 | 10,277 |
| memory [bytes per node] | 554 | 554 | 414 | 414 |

EulerTree with integer positions is the fastest combination in nearly every row; with rational positions it renumbers least. In C# a position takes the same memory in both kinds (two 64-bit numbers), so the memory differs only between one list and two. One row stands out: "reaches all" on an EulerTree with rational positions (0.062 µs) is slower than on DTree, because its second coordinate, the end of a block, is looked up through the closing cell before the fractions are compared.

## Measurements

Python 3.13, Claude's Linux workspace (Oct 30, 2026), `python -m triordinal.dtree.bench --prior-art`. Timings in Python mostly reflect the interpreter; the C# measurements below are the ones to compare methods by.

Insertions with one query each (20,000 nodes; µs per step, best of three runs):

| depth | DTree | Euler tour, rational | Euler tour, integer | parent walk |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 2.52 | 1.85 | 1.97 | 0.29 |
| 1,000 | 3.35 | 2.19 | 1.96 | 12.86 |
| 10,000 | 4.76 | 2.92 | 2.65 | 84.16 |

(The parent walk from the first table of the same run; the other columns from the second.)

Insertions and queries in batches of *b* (20,000 nodes, depth 1,000; µs per insertion with its share of the queries):

| batch b | DTree | Euler tour | pre/post, lazy | parent walk |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 3.46 | 2.52 | 335.76 | 12.72 |
| 100 | 3.49 | 2.39 | 32.82 | 12.73 |
| 1,000 | 3.65 | 2.52 | 3.34 | 12.49 |

And/or queries (100,000 nodes, depth 1,000, set of 1,000 nodes; µs per query):

| question | DTree | Euler tour | pre/post |
| --- | ---: | ---: | ---: |
| reaches all | 0.73 | 0.51 | 0.31 |
| reaches some | 2.92 | 1.81 | 0.72 |
| reached by all | 0.69 | 0.46 | 0.26 |
| reached by some | 1.99 | 1.10 | 0.55 |

Single queries on a built random tree of 100,000 nodes (1,000,000 pairs of handles): DTree 0.431 µs, Euler tour rational 0.424 µs, integer 0.331 µs.

Renumberings while building trees of 100,000 nodes, by kind of position (Python's limits; they do not depend on the machine):

| shape | DTree, Q1 / Q2 | rational | integer | float | decimal |
| --- | ---: | ---: | ---: | ---: | ---: |
| random | 0 / 0 | 0 | 712 | 2,512 | 4 |
| chain | 4,346 / 4,346 | 4,346 | 22,281 | 24,878 | 26,416 |
| star (root) | 0 / 0 | 0 | 20,760 | 4,863 | 2,724 |
| star (inner node) | 0 / 0 | 0 | 19,075 | 10,834 | 6,895 |
| alternating | 2,940 / 2,940 | 3,570 | 23,831 | 27,987 | 29,106 |
| top-down comb | 129 / 129 | 129 | 6,475 | 7,700 | 1,129 |

Growing one list of 100,000 cells (renumberings: rational / integer / float / decimal): append 0 / 9,227 / 0 / 0; prepend 0 / 10,328 / 0 / 0; both ends alternating 0 / 9,671 / 0 / 0; one gap from one side 0 / 11,446 / 2,347 / 1,015; one gap from alternating sides 2,172 / 11,041 / 12,396 / 13,196; hot spots 0 / 2,642 / 0 / 0.

Memory per node (random tree of 100,000 nodes, tracemalloc): DTree 801 bytes, Euler tour 477, pre/post numbers 286.

## Measurements in C#

.NET 9, measured by Enis Olgac on his NUC (Intel, Windows 10.0.22631), Oct 30, 2026, `-- bench prior-art`; full reports in [`benchmarks/csharp/2026-10-30_09-23.md`](../benchmarks/csharp/2026-10-30_09-23.md) (first run) and [`benchmarks/csharp/2026-10-30_09-53.md`](../benchmarks/csharp/2026-10-30_09-53.md) (all kinds and placement rules; the tables below). Single runs of the insertions with queries vary by about a third from run to run; the renumbering counts do not vary.

Insertions with one query each (100,000 nodes, node handles; µs per step, best of three runs):

| depth | DTree | Euler tour | parent walk |
| ---: | ---: | ---: | ---: |
| 10 | 0.993 | 0.658 | 0.223 |
| 1,000 | 1.207 | 0.910 | 1.150 |
| 10,000 | 2.011 | 1.295 | 14.070 |
| 100,000 | 2.764 | 1.121 | 79.594 |

Insertions and queries in batches of *b* (100,000 nodes, depth 1,000; µs per insertion with its share of the queries):

| batch b | DTree | Euler tour | pre/post, lazy | parent walk |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 1.217 | 0.828 | 45.648 | 1.301 |
| 100 | 1.256 | 0.823 | 4.957 | 0.804 |
| 1,000 | 1.374 | 0.830 | 0.603 | 1.202 |

And/or queries (100,000 nodes, depth 1,000, set of 1,000 nodes; µs per query):

| question | DTree | Euler tour | pre/post |
| --- | ---: | ---: | ---: |
| reaches all | 0.042 | 0.030 | 0.003 |
| reaches some | 0.288 | 0.258 | 0.103 |
| reached by all | 0.039 | 0.027 | 0.003 |
| reached by some | 0.210 | 0.162 | 0.050 |

Memory per node (random tree of 100,000 nodes, GC.GetTotalMemory): DTree 554 bytes, Euler tour 303, pre/post numbers 63.

Kinds of positions, the same Euler tour (100,000 nodes, node handles; µs per step, best of three runs):

| depth | DTree | rational | integer | double | decimal |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 1.424 | 0.570 | 0.822 | 0.865 | 1.358 |
| 1,000 | 1.535 | 0.843 | 0.636 | 1.342 | 1.312 |
| 10,000 | 1.769 | 1.477 | 0.636 | 1.093 | 1.692 |
| 100,000 | 2.949 | 1.295 | 0.702 | 0.922 | 2.517 |

Single queries on a built random tree of 100,000 nodes (1,000,000 pairs of handles): DTree 0.058 µs; Euler tour rational 0.054, integer 0.035, double 0.035, decimal 0.068.

Renumberings while building trees of 100,000 nodes:

| shape | rational | integer | double | decimal (List.cs rule) |
| --- | ---: | ---: | ---: | ---: |
| random | 2 | 276 | 1,694 | 0 |
| chain | 6,895 | 22,281 | 24,878 | 25,468 |
| star (root) | 0 | 20,760 | 4,863 | 2,619 |
| star (inner node) | 0 | 19,075 | 10,834 | 6,643 |
| alternating | 5,713 | 23,831 | 27,987 | 29,040 |
| top-down comb | 206 | 6,475 | 7,700 | 5,679 |

C# renumbers rational positions earlier than Python (denominators above 2⁴⁰ instead of 2⁶⁴), hence its higher counts for the chain. The placement rules (midpoint against the List.cs rule in base 2 and 10, for integer, double and decimal) are in the second report.
