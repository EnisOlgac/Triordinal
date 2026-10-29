# Triordinal.DList

The list shared by [Triordinal](https://github.com/EnisOlgac/Triordinal)'s DTree and DGraph: a doubly linked list of names with rational positions, so that "does a come before b?" is a single comparison, O(1).

```
dotnet add package Triordinal.DList
```

A new element gets the mediant of its neighbors, so normally no other element moves. Only when a denominator would exceed 2^40 is the smallest surrounding region with enough room renumbered; larger regions must be sparser before they are accepted (as in Bender et al., ESA 2002). Rational positions were Enis Olgac's idea. Namespace `Triordinal`.

Most users install `Triordinal.DTree` (or later `Triordinal.DGraph`), which pulls this package in. MIT License.
