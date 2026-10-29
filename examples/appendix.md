### Insertion History and Symbolic Projection

The following example demonstrates how symbolic projections (`Q1`, `Q2`) respond to insertion order.

We insert a node `X` as a fourth child of the root (`01`), with children `Y` and `Z`. All other edges remain unchanged. We test three insertion points for `(01, X)`:

| Test | Insertion Position | `Q1` (Build Order) | `Q2` (Mirror Order) |
|------|--------------------|--------------------|----------------------|
| A (test22) | First           | `X, Y, Z` first   | `X, Z, Y` last       |
| B (test21) | Middle          | Between `08` and `03` | After `03`, before `11` |
| C (test23) | Last            | `X, Y, Z` last    | `X, Z, Y` first      |

Although the projections differ, the tree structure (parent–child relationships) remains invariant.

This confirms that `Q1` and `Q2` **capture symbolic construction history**, not just topology.

![Insertion A](./test22.png)
![Insertion B](./test21.png)
![Insertion C](./test23.png)
