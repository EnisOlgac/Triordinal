# Triordinal.DList

The list shared by [Triordinal](https://github.com/EnisOlgac/Triordinal)'s DTree and DGraph: a doubly linked list of names with rational positions, so that "does a come before b?" is a single comparison, O(1).

```
dotnet add package Triordinal.DList
```

A new element gets the mediant of its neighbors, so normally no other element moves. Positions are pairs of 64-bit integers. Only when a denominator would exceed 2^40, or a numerator 2^61, is the smallest surrounding region with enough room renumbered with fractions k/2^20; larger regions must be sparser before they are accepted (as in Bender et al., ESA 2002). Rational positions were Enis Olgac's idea. Namespace `Triordinal`.

A list may also hold unnamed cells, which have a position but no name; enumeration, `Next`/`Prev` and all lookups by name pass over them. DTree uses them as the closing cells that mark the end of each subtree.

Most users install `Triordinal.DTree` (or later `Triordinal.DGraph`), which pulls this package in. MIT License.
