# Triordinal.DTree

C# implementation of `DTree`, the incremental encoding of the topology of directed trees. Since 3.0.0 a DTree keeps one projection, Q1 (the pre-order), and the structure of the tree in its vertices: each vertex knows its parent, its kids list (read left to right from one end, right to left from the other), its place in its parent's list, and its cell in Q1. Node *u* reaches node *v* exactly when *v* lies after *u* in Q1 and before *u*'s delimiter, its right sibling or, for a last kid, its parent's delimiter. Almost every query is decided locally, and a sequence of only kids is crossed in one step. How one list and two lists differ, and the way to 3.0: [One list and two lists](https://github.com/EnisOlgac/Triordinal/blob/main/docs/one-and-two-lists.md).

```
dotnet add package Triordinal.DTree
```

```csharp
using DirectedTrees;   // DTree, DNode, constructed nodes

var t = new DTree("P1");
t.Insert("A", "B");     // the first insert makes A the root
t.Insert("B", "C");
t.CanReach("A", "C");   // true
t.PathToRoot("C");      // ["C", "B", "A"]

// Node handles skip the lookup by name:
DNode a = t.GetNode("A"), c = t.GetNode("C");
t.CanReach(a, c);       // true
DNode e = t.InsertFirst(a, "E");   // E becomes A's first kid

// And/or queries on the topology, with constructed nodes built for the query:
t.Insert("A", "D");
t.VMin(new[] { "C", "D" }).ReachesAll("A");      // true
t.UMin(new[] { "B", "D" }).ReachedBySome("C");   // true
```

`new DTree("P1", Positions.Integer)` gives integer positions instead of the default rational ones. Every operation checks its arguments before it changes anything, so an operation that throws leaves the tree as it was.

DTree 3.0 is not compatible with 2.x. The earlier encodings remain in the package for comparison, with their own API: `DirectedTrees.TwoLists.DTree` (DTree 2.x on Q1 and Q2) and `Triordinal.DTree.Euler.EulerTree` (one list with closing cells).

- Repository, Python implementation and documentation: https://github.com/EnisOlgac/Triordinal
- Paper: E. Olgac, "Topology and Structure of Directed Trees: An Incremental Encoding," IntechOpen, 2025. https://doi.org/10.5772/intechopen.1013408
- License: MIT
