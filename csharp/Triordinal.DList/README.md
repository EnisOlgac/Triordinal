# Triordinal.DList

The list shared by [Triordinal](https://github.com/EnisOlgac/Triordinal)'s DTree and DGraph: a doubly linked list of names with rational positions, so that "does a come before b?" is a single comparison, O(1).

```
dotnet add package Triordinal.DList
```

A new element gets the mediant of its neighbors, so normally no other element moves. Positions are pairs of 64-bit integers. Only when a mediant cannot be stored, its denominator or numerator exceeding 2^61, is the smallest surrounding region with enough room renumbered with fractions k/2^20 (the same bounds as the Python reference); larger regions must be sparser before they are accepted (as in Bender et al., ESA 2002). A block of cells that is cut and pasted elsewhere is placed as a whole and renumbers a region only if it does not fit. Rational positions were Enis Olgac's idea. Namespace `Triordinal`.

`new DList("Q", Positions.Integer)` gives integer positions instead: midpoints in [0, 2^62], as in classical order maintenance, relabeled with the same density rule. They are faster to compare; rational positions are renumbered far less often.

A list may also hold unnamed cells, which have a position but no name; enumeration, `Next`/`Prev` and all lookups by name pass over them. DTree uses them as the closing cells that mark the end of each subtree.

Most users install `Triordinal.DTree` (or later `Triordinal.DGraph`), which pulls this package in. MIT License.
