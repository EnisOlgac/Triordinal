# DTree Explorer (triordinal-dtree-explorer)

Part of [Triordinal](https://github.com/EnisOlgac/Triordinal), next to DList and DTree, with the same version number. Versions up to 1.3.3 were published as `dtree-explorer` from [DTree-Explorer](https://github.com/EnisOlgac/DTree-Explorer) (archive: [doi:10.5281/zenodo.23701538](https://doi.org/10.5281/zenodo.23701538)).

Encode a directed tree with [DTree](https://github.com/EnisOlgac/Triordinal) and watch it happen, edge by edge. The Explorer draws the tree, places every node in the plane at its rank in Q1 and Q2, lists the projections with the positions the library stores, and answers reachability questions by clicking.

The card *Encoding*, below the tree description, offers two choices:

- **Lists:** **DTree 3.0** (the default) keeps one list, Q1, and the structure in the nodes: a node's block runs from its own cell to just before its *delimiter*, its next sibling or, for a last child, its parent's delimiter, and *u* reaches *v* exactly when *v* lies inside *u*'s block. View 3 shows Q1 with each node's delimiter below it, and picking two nodes names the step of the query that decides. **DTree 2.x** keeps two lists, Q1 and Q2: *u* reaches *v* exactly when *u* comes before *v* in both. **EulerTree** keeps Q1 alone with a closing cell after the subtree of every node with children (the Euler tour); view 3 shows Q1 as it grows, bracketed: `A[` opens the block of A, `]A` closes it. The plane is the same for all three: DTree 3.0 reads Q2 from the children right to left, EulerTree from its block ends.
- **Positions:** rational (fractions; a new cell takes the mediant of its neighbors) or integer (a new cell takes the midpoint of its neighbors' labels in [0, 2^62]).

The page remembers both choices.

On PyPI the Explorer is `triordinal-dtree-explorer`; it continues `dtree-explorer` (up to 1.3.3). The command is still `dtree-explorer`.

Every tree is computed by the published library, [triordinal-dtree](https://pypi.org/project/triordinal-dtree/) from [Triordinal](https://github.com/EnisOlgac/Triordinal) (formerly dtree-encoding); the Explorer only shows what it computes.

## Three ways to use it

**Online:** [dtree.digraphs.net](https://dtree.digraphs.net/), nothing to install.

**As a Python program**, offline, with the library installed on your machine:

```
pip install triordinal-dtree-explorer
dtree-explorer
```

The command starts a small server on 127.0.0.1 and opens the page in your browser; stop it with Ctrl+C. It installs the matching triordinal-dtree. Options: `--port 8765`, `--no-browser`, `--save explorer.html` (write the page as one file).

**As a single file:** download `DTree-Explorer.html` from the [latest Triordinal release](https://github.com/EnisOlgac/Triordinal/releases/latest) and open it in a browser. It loads Python (Pyodide) from cdn.jsdelivr.net and triordinal-dtree from pypi.org, so it needs an internet connection.

## Input

One line per instruction; lines starting with `#` are comments.

| Line | Meaning |
|---|---|
| `p: c1; c2` | c1 and c2 become the last children of p |
| `s > c1; c2` | c1 goes directly after its sibling s, then c2 after c1 |
| `s < c1; c2` | c1 and c2 go directly before s, in that order |

The examples include the trees of the paper: the introductory example, Figure 1, the generalized insertion of Section 4.1 (Case A, before; Case B, after) and Appendix A, whose three variants appear twice: once by the order of the input lines, once with `<` and `>`. Both give the same projections.

## Privacy

Your tree stays on your computer. Only the online copy at dtree.digraphs.net counts visits, with [GoatCounter](https://www.goatcounter.com/): no cookies, no personal data. The package and the release file count nothing.

## Building

The Explorer lives in `python/explorer` of the Triordinal repository and is built from the repository's own DList and DTree, so the page always matches the library of the same commit; nothing needs to be installed. `src/template.html` is the page, `dtree_explorer/bridge.py` the Python part it runs, `src/build.py` assembles `dtree_explorer/explorer.html` (package and release) and `site/index.html` (dtree.digraphs.net), with the examples from the repository's `examples/`. In `python/explorer`: `python src/build.py`, tests `python -m unittest discover -s tests`. The publish workflow rebuilds the page, publishes the package after DList and DTree, and attaches the page to the release as `DTree-Explorer.html`.

## Background

E. Olgac, "Topology and Structure of Directed Trees: An Incremental Encoding," IntechOpen, 2025. doi: [10.5772/intechopen.1013408](https://doi.org/10.5772/intechopen.1013408).

## Citation

E. Olgac, *DTree Explorer: Watching the Incremental Encoding of Directed Trees*, software, 2026. doi: [10.5281/zenodo.23701538](https://doi.org/10.5281/zenodo.23701538) (all versions). See `CITATION.cff`.

## License

MIT. Design and concept: Enis Olgac. The Explorer was written with Claude (Anthropic).
