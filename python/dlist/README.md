# DList for Python (triordinal-dlist)

The list shared by [Triordinal](https://github.com/EnisOlgac/Triordinal)'s DTree and DGraph: a doubly linked list of names with rational positions, so that "does a come before b?" is a single comparison, O(1).

```
pip install triordinal-dlist
```

```python
from triordinal.dlist import DList

q = DList("Q")
q.insert_after("a", "[")      # "[" is the start marker (SOURCE)
q.insert_after("b", "a")
q.precedes("a", "b")          # True
```

A new element gets the mediant (a+c)/(b+d) of its neighbors a/b and c/d, so normally no other element moves. Only when a mediant cannot be stored, its denominator or numerator exceeding 2⁶¹ (the bound of the C# version, so that both renumber alike), is the smallest surrounding region with enough room renumbered with fractions k/2²⁰; larger regions must be sparser before they are accepted (as in Bender et al., ESA 2002). A block of cells that is cut and pasted elsewhere is placed as a whole and renumbers a region only if it does not fit. Rational positions were Enis Olgac's idea.

`DList("Q", positions="integer")` gives integer positions instead: midpoints in [0, 2⁶²], as in classical order maintenance, relabeled with the same density rule. They are faster to compare; rational positions are renumbered far less often.

A list may also hold unnamed cells, which have a position but no name; iteration, `next`/`prev` and all lookups by name pass over them. DTree uses them as the closing cells that mark the end of each subtree.

Most users install `triordinal-dtree` (or later `triordinal-dgraph`), which pulls this package in. MIT License.
