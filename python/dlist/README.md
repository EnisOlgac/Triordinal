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

A new element gets the mediant (a+c)/(b+d) of its neighbors a/b and c/d, so normally no other element moves. Only when a denominator would exceed 64 bits is the smallest surrounding region with enough room renumbered; larger regions must be sparser before they are accepted (as in Bender et al., ESA 2002). Rational positions were Enis Olgac's idea.

A list may also hold unnamed cells, which have a position but no name; iteration, `next`/`prev` and all lookups by name pass over them. DTree uses them as the closing cells that mark the end of each subtree.

Most users install `triordinal-dtree` (or later `triordinal-dgraph`), which pulls this package in. MIT License.
