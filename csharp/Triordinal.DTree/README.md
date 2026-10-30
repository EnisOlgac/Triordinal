# Triordinal.DTree

C# implementation of `DTree`, the incremental encoding of the topology of directed trees by two projections Q1 and Q2: node *u* reaches node *v* if and only if *u* precedes *v* in both. Reachability, including and/or queries over sets of nodes, is answered in O(1) or O(log k) by comparing positions, and stays valid under insertions without recomputation, because the insertion points of a new node are known in advance.

```
dotnet add package Triordinal.DTree
```

```csharp
using DirectedTrees;   // DTree, DNode, constructed nodes, Projection (Q1, Q2)

var t = new DTree("P1");
t.Insert("A", "B");
t.Insert("B", "C");
t.CanReach("A", "C");   // true
t.PathToRoot("C");      // ["C", "B", "A"]

// Node handles skip the lookup by name:
DNode a = t.GetNode("A"), c = t.GetNode("C");
t.CanReach(a, c);       // true, two position comparisons

// And/or queries on the topology, with constructed nodes:
t.Insert("A", "D");
t.VMin(new[] { "C", "D" }).ReachesAll("A");      // true
t.UMin(new[] { "B", "D" }).ReachedBySome("C");   // true
```

`Triordinal.DTree.Euler.EulerTree` is the tree on one list: DTree's Q1 with its closing cells, the classical Euler-tour encoding, with DTree's API except Q2. For trees it is faster than DTree's two lists and needs less memory. Both take `Positions.Integer` for integer positions instead of the default rational ones.

```csharp
using Triordinal.DTree.Euler;

var e = new EulerTree("E1");
e.Insert("A", "B");
e.CanReach("A", "B");   // true
```

`new DTree("P1", strict: true)` makes queries throw for names that are not in the tree instead of answering false. Every operation checks its arguments before it changes anything, so an operation that throws leaves the tree as it was.

- Repository, Python implementation and documentation: https://github.com/EnisOlgac/Triordinal
- Paper: E. Olgac, "Topology and Structure of Directed Trees: An Incremental Encoding," IntechOpen, 2025. https://doi.org/10.5772/intechopen.1013408
- License: MIT
