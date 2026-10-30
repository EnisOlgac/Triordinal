"""Performance benchmarks for DTree.

Usage, after ``pip install triordinal-dtree`` (or from the repository's python/ folder,
where ``python benchmarks/bench.py`` does the same):

    python -m triordinal.dtree.bench                 # sizes 10,000 and 100,000
    python -m triordinal.dtree.bench 1000 1000000    # custom sizes
    python -m triordinal.dtree.bench --quick         # small sizes, a few seconds
    python -m triordinal.dtree.bench --dynamic       # only the dynamic updates and the tree view
    python -m triordinal.dtree.bench --review        # only the patterns from the review of 1.8.0
    python -m triordinal.dtree.bench --prior-art     # only the comparison with prior art
    python -m triordinal.dtree.bench --euler         # only DTree against EulerTree, by kind of position
    python -m triordinal.dtree.bench --moves         # only moving subtrees (cut_n_paste)
    python -m triordinal.dtree.bench --note "idle machine after restart"   # remark for the report
    python -m triordinal.dtree.bench --no-save       # do not write a report

Every run also writes its tables as a Markdown report, named after date and time
(e.g. 2026-10-17_14-18.md), with a header giving the DTree and Python versions, the
operating system and the processor: to benchmarks/python/ at the repository root when
run from a clone, otherwise to benchmarks/python/ in the current directory.

For each tree shape it reports the build time and how often positions in Q1
and Q2 had to be renumbered, then times the queries and structural changes.
Finally it compares reachability with the parent walk of classical doubly linked
trees, for single pairs and for and/or queries (VMin, VMax, UMin, UMax), over increasing depth,
and under dynamic updates, with insertions and queries alternating (including static
pre/post numbers recomputed after each insertion), and in a use case: a tree view whose
nodes are inserted, collapsed and expanded while rows are shown. The last section times the
complexity patterns pointed out in Onur Safi's review of DTree 1.8.0, and the memory per node.
A last section compares DTree with prior art: the parenthesis (Euler-tour) encoding on one list
with the same rational positions, and pre/post numbers recomputed lazily (see prior_art.py).
Timings depend on the machine; the renumbering counts do not.
"""

import argparse
import datetime
import gc
import io
import os
import platform
import random
import sys
import time
import tracemalloc

import triordinal.dtree as _pkg
from triordinal.dtree import SINK, SOURCE, DList, DTree
from triordinal.dtree.euler import EulerTree
from triordinal.dtree.prior_art import EulerTour, EulerTourInt, EulerTourNum, IntList, NumList, PrePostNumbers


def _base_dir():
    """The repository root when run from a clone, otherwise the current directory."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):                      # python/dtree/triordinal/dtree/bench.py -> repository root
        if os.path.isdir(os.path.join(d, "csharp")) and os.path.isdir(os.path.join(d, "python")):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


REPO = _base_dir()
REPORTS = os.path.join(REPO, "benchmarks", "python")


class _Tee(io.TextIOBase):
    """Writes to the console and keeps a copy for the report."""

    def __init__(self, console):
        self.console, self.copy = console, io.StringIO()

    def write(self, text):
        self.console.write(text)
        self.console.flush()
        self.copy.write(text)
        return len(text)

    def flush(self):
        self.console.flush()


def _processor():
    name = platform.processor() or platform.machine()
    try:  # Linux: the model name is more telling than the architecture
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return name


def write_report(body, started, args_text, note):
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, started.strftime("%Y-%m-%d_%H-%M") + ".md")
    head = [
        f"# DTree benchmarks, Python—{started.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- DTree (triordinal-dtree) {_pkg.__version__}, Python {sys.version.split()[0]} ({platform.python_implementation()})",
        f"- {platform.system()} {platform.release()} ({platform.platform()})",
        f"- Processor: {_processor()}, {os.cpu_count()} logical cores",
        f"- Command: `python -m triordinal.dtree.bench{(' ' + args_text) if args_text else ''}`",
    ]
    if note:
        head.append(f"- Note: {note}")
    lines = body.splitlines()
    if lines and lines[0].startswith("DTree benchmarks"):
        lines = lines[1:]             # the console title is replaced by the header above
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head) + "\n" + "\n".join(lines).rstrip() + "\n")
    return path

SHAPES = {
    # name: function(i, names, rnd) -> parent of the new node n{i}
    "random": lambda i, names, rnd: rnd.choice(names),
    "chain": lambda i, names, rnd: names[-1],
    "star (root)": lambda i, names, rnd: "n0",
    "star (inner node)": lambda i, names, rnd: "n1",
    # worst case for rational positions: always the newer half-gap, alternating sides
    "alternating": lambda i, names, rnd: f"n{2 * ((i - 1) // 2)}",
    # a chain of 3,000, then new leaves under the spine nodes from the top down, repeatedly:
    # finding the end of a subtree by walking down the last children would be O(depth) here
    "top-down comb": lambda i, names, rnd: names[-1] if i < 3000 else f"n{(i - 3000) % 3000}",
}


def build(shape, n, seed=1):
    rnd = random.Random(seed)
    t, names = DTree("B"), ["n0"]
    pick = SHAPES[shape]
    start = time.perf_counter()
    for i in range(1, n):
        if shape == "star (inner node)" and i <= 2:
            parent = "n0"  # n1 and n2 under the root, so n1 has a right neighbor
        else:
            parent = pick(i, names, rnd)
        t.insert(parent, f"n{i}")
        names.append(f"n{i}")
    return t, names, time.perf_counter() - start


def stats(q):
    return q.renumber_count, q.renumber_moved


def row(*cells):
    print("| " + " | ".join(str(c) for c in cells) + " |")


def bench_build(sizes):
    print("\n### Building trees\n")
    row("shape", "nodes", "time [s]", "renumberings Q1 / Q2", "positions moved per insertion")
    row("---", "---:", "---:", "---:", "---:")
    for shape in SHAPES:
        for n in sizes:
            t, _, dt = build(shape, n)
            c1, m1 = stats(t.Q1)
            c2, m2 = stats(t.Q2)
            row(shape, f"{n:,}", f"{dt:.2f}", f"{c1:,} / {c2:,}", f"{(m1 + m2) / (2 * n):.2f}")


def bench_lists(sizes):
    print("\n### Growing a single list (DList)\n")
    row("pattern", "nodes", "time [s]", "renumberings")
    row("---", "---:", "---:", "---:")
    for pattern in ("append", "prepend", "alternate"):
        for n in sizes:
            q = DList("Q")
            start = time.perf_counter()
            for i in range(n):
                right = pattern == "append" or (pattern == "alternate" and i % 2)
                if right:
                    q.insert_before(f"v{i}", SINK)
                else:
                    q.insert_after(f"v{i}", SOURCE)
            row(pattern, f"{n:,}", f"{time.perf_counter() - start:.2f}", f"{q.renumber_count:,}")


def bench_operations(n, queries=1_000_000):
    print(f"\n### Queries and changes on a random tree of {n:,} nodes\n")
    row("operation", "count", "time [s]", "per operation [µs]")
    row("---", "---:", "---:", "---:")
    rnd = random.Random(2)

    def timed(name, count, fn):
        start = time.perf_counter()
        fn()
        dt = time.perf_counter() - start
        row(name, f"{count:,}", f"{dt:.2f}", f"{dt / count * 1e6:.1f}")

    t, names, _ = build("random", n)
    pairs = [(rnd.choice(names), rnd.choice(names)) for _ in range(queries)]
    timed("can_reach (names)", queries, lambda: sum(t.can_reach(u, v) for u, v in pairs))
    handles = [(t.get_node(u), t.get_node(v)) for u, v in pairs]
    timed("can_reach (handles)", queries, lambda: sum(t.can_reach(u, v) for u, v in handles))
    timed("depth", len(names), lambda: sum(t.depth(v) for v in names))

    k = max(1, n // 10)
    t, names, _ = build("random", n)
    victims = rnd.sample(names[1:], k)
    timed("delete", k, lambda: [t.delete(v) for v in victims])

    t, names, _ = build("random", n)
    moves = []
    while len(moves) < max(1, n // 100):
        u, p = rnd.choice(names[1:]), rnd.choice(names)
        moves.append((u, p))

    def do_moves():
        for u, p in moves:
            if t.contains(u) and t.contains(p) and u != p and not t.can_reach(u, p):
                t.cut_n_paste(u, p)

    timed("cut_n_paste", len(moves), do_moves)

    t, names, _ = build("random", n)
    leaves = [v for v in names if t.is_leaf(v)][: max(1, n // 10)]
    parents = list({t.get_parent(v) for v in leaves if t.get_parent(v)})
    timed("delete_subtree", len(parents), lambda: [t.delete_subtree(v) for v in parents if t.contains(v) and not t.is_root(v)])


def build_with_depth(n, depth, seed=1):
    """A spine (chain) of `depth` nodes; all other nodes hang at random under spine nodes."""
    rnd = random.Random(seed)
    t, names = DTree("D"), ["n0"]
    for i in range(1, n):
        if i < depth:
            parent = names[-1]                       # extend the spine
        else:
            parent = names[rnd.randrange(min(depth, len(names)))]
        t.insert(parent, f"n{i}")
        names.append(f"n{i}")
    return t, names


def parent_walk(parent, u, v):
    """What classical doubly linked trees do: climb from v towards the root, looking for u."""
    w = parent.get(v)
    while w is not None:
        if w == u:
            return True
        w = parent.get(w)
    return False


def ancestors_in(parent, v, members):
    """Climb once from v towards the root and count the ancestors of v that lie in members."""
    hits, w = 0, parent.get(v)
    while w is not None:
        if w in members:
            hits += 1
        w = parent.get(w)
    return hits


def bench_depth(n, depths, queries):
    print(f"\n### Reachability by depth: DTree vs parent walk ({n:,} nodes, {queries:,} random pairs)\n")
    row("depth", "DTree [µs]", "parent walk [µs]", "factor")
    row("---:", "---:", "---:", "---:")
    for depth in depths:
        t, names = build_with_depth(n, depth)
        parent = t._parent
        rnd = random.Random(2)
        pairs = [(rnd.choice(names), rnd.choice(names)) for _ in range(queries)]
        start = time.perf_counter()
        a = [t.can_reach(u, v) for u, v in pairs]
        d = time.perf_counter() - start
        start = time.perf_counter()
        b = [parent_walk(parent, u, v) for u, v in pairs]
        w = time.perf_counter() - start
        assert a == b
        row(f"{depth:,}", f"{d / queries * 1e6:.2f}", f"{w / queries * 1e6:.2f}", factor(w, d))


def bench_sets(n, depths, k, queries):
    print(f"\n### And/or queries: constructed nodes vs parent walk ({n:,} nodes, set of {k:,} nodes, {queries:,} query nodes)\n")
    row("depth", "question", "DTree [µs]", "parent walk [µs]", "factor")
    row("---:", "---", "---:", "---:", "---:")
    for depth in depths:
        t, names = build_with_depth(n, depth)
        parent = t._parent
        rnd = random.Random(4)
        S = rnd.sample(names, k)
        U = [rnd.choice(names) for _ in range(queries)]
        start = time.perf_counter()
        vmin, vmax, umin, umax = t.vmin(S), t.vmax(S), t.umin(S), t.umax(S)
        build = time.perf_counter() - start
        members = set(S)
        # "reaches": climb from every member looking for u. "reached by": climb once from u,
        # looking each ancestor up in a hash set of the members (the best a parent walk can do).
        for name, v_q, walk_q in (
            ("reaches all", vmin.reaches_all, lambda u: all(parent_walk(parent, u, v) for v in S)),
            ("reaches some", vmax.reaches_some, lambda u: any(parent_walk(parent, u, v) for v in S)),
            ("reached by all", umax.reached_by_all, lambda u: ancestors_in(parent, u, members) == len(members)),
            ("reached by some", umin.reached_by_some, lambda u: ancestors_in(parent, u, members) > 0),
        ):
            start = time.perf_counter()
            a = [v_q(u) for u in U]
            d = time.perf_counter() - start
            start = time.perf_counter()
            b = [walk_q(u) for u in U]
            w = time.perf_counter() - start
            assert a == b, name
            row(f"{depth:,}", name, f"{d / queries * 1e6:.2f}", f"{w / queries * 1e6:.1f}", factor(w, d))
    print(f"\n(Building VMin, VMax, UMin and UMax for {k:,} nodes: {build * 1e3:.1f} ms, once per set.)")


def factor(slow, fast):
    return f"{slow / fast:.1f}×" if slow < 10 * fast else f"{slow / fast:,.0f}×"


def dynamic_workload(n, depth, queries_per_insert, seed=5):
    """The same sequence for every contender: insertions (a spine of `depth` nodes, the
    others attached at random to spine nodes) with random queries among the nodes present."""
    rnd = random.Random(seed)
    steps = []
    for i in range(1, n):
        parent = i - 1 if i < depth else rnd.randrange(min(depth, i))
        qs = [(rnd.randrange(i + 1), rnd.randrange(i + 1)) for _ in range(queries_per_insert)]
        steps.append((parent, i, qs))
    return steps


def run_dtree(steps):
    """DTree with node handles (insert returns the new node's handle)."""
    t, answers = DTree("D"), []
    nodes = [None] * (len(steps) + 1)
    for p, c, qs in steps:
        if c == 1:
            nodes[1] = t.insert("n0", "n1")
            nodes[0] = t.get_node("n0")
        else:
            nodes[c] = t.insert(nodes[p], f"n{c}")
        for u, v in qs:
            answers.append(t.can_reach(nodes[u], nodes[v]))
    return answers


def run_parent_walk(steps):
    parent, answers = {}, []
    for p, c, qs in steps:
        parent[c] = p
        for u, v in qs:
            answers.append(parent_walk(parent, u, v))
    return answers


def run_static_numbers(steps):
    """Pre- and post-order numbers from a traversal, recomputed before a query whenever the
    tree has changed: O(1) queries, but every insertion invalidates all numbers."""
    children, answers = {}, []
    pre = post = None
    for p, c, qs in steps:
        children.setdefault(p, []).append(c)
        pre = None                                     # the insertion invalidates the numbers
        for u, v in qs:
            if pre is None:
                pre, post, clock = {}, {}, 0
                stack = [(0, False)]
                while stack:
                    x, done = stack.pop()
                    if done:
                        post[x] = clock
                        clock += 1
                        continue
                    pre[x] = clock
                    clock += 1
                    stack.append((x, True))
                    stack.extend((k, False) for k in reversed(children.get(x, ())))
            answers.append(pre[u] < pre[v] and post[v] < post[u])
    return answers


def timed(run, steps):
    start = time.perf_counter()
    answers = run(steps)
    return time.perf_counter() - start, answers


def best(run, steps):
    """Best of three runs, or a single run if it takes over two seconds (noise is small then)."""
    sec, answers = timed(run, steps)
    if sec < 2:
        for _ in range(2):
            sec = min(sec, timed(run, steps)[0])
    return sec, answers


def bench_dynamic(n, depths, static_sizes, static_depths=(100, 1_000)):
    timed(run_dtree, dynamic_workload(1_000, 10, 1))                 # warm-up
    timed(run_parent_walk, dynamic_workload(1_000, 10, 1))
    print(f"\n### Dynamic updates: insertions and queries alternating ({n:,} nodes)\n")
    print("A step is one insertion followed by 1 or 10 queries between random nodes present at "
          "that moment; µs per step, best of three runs.\n")
    row("depth", "DTree, 1 query", "parent walk, 1 query", "factor",
        "DTree, 10 queries", "parent walk, 10 queries", "factor")
    row("---:", "---:", "---:", "---:", "---:", "---:", "---:")
    for depth in depths:
        cells = [f"{depth:,}"]
        for q in (1, 10):
            steps = dynamic_workload(n, depth, q)
            d, a = best(run_dtree, steps)
            w, b = best(run_parent_walk, steps)
            assert a == b
            cells += [f"{d / len(steps) * 1e6:.2f}", f"{w / len(steps) * 1e6:.2f}", factor(w, d)]
        row(*cells)
    print("\n### Dynamic updates with static pre/post numbers, recomputed after each insertion "
          "(1 query per insertion)\n")
    print("The tree keeps the given depth as it grows: more nodes make it wider, not deeper. "
          "Total time in ms.\n")
    row("depth", "nodes", "DTree [ms]", "parent walk [ms]", "static numbers [ms]")
    row("---:", "---:", "---:", "---:", "---:")
    for depth in static_depths:
        for m in static_sizes:
            steps = dynamic_workload(m, depth, 1)
            d, a = best(run_dtree, steps)
            w, b = best(run_parent_walk, steps)
            r, c = timed(run_static_numbers, steps)
            assert a == b == c
            row(f"{depth:,}", f"{m:,}", f"{d * 1e3:,.1f}", f"{w * 1e3:,.1f}", f"{r * 1e3:,.0f}")


# -- use case: a tree view with expand/collapse --------------------------------------------

def tree_view_workload(n, depth, steps, seed=6):
    """Changes to a tree built by build_with_depth(n, depth): each step either inserts a leaf
    under a random spine node or toggles (collapses or expands) a random spine node, and then
    names a random node v whose row is to be shown."""
    rnd = random.Random(seed)
    ops, size = [], n
    for _ in range(steps):
        if rnd.random() < 0.5:
            op = ("insert", f"n{rnd.randrange(depth)}", f"n{size}")
            size += 1
        else:
            op = ("toggle", f"n{rnd.randrange(depth)}", None)
        ops.append(op + (f"n{rnd.randrange(size)}",))
    return ops


def tree_view_dtree(t, ops, rows):
    """DTree: the collapsed nodes are one UMin. The visible row that contains v is
    collapsed.covering(v) (v itself if None); the rows below it follow Q1, jumping over the
    subtree of every collapsed node with subtree_last."""
    collapsed, out = t.umin(), []
    nxt, last = t.next_in_q1, t.subtree_last
    for kind, a, b, v in ops:
        if kind == "insert":
            t.insert(a, b)
        elif a in collapsed:
            collapsed.discard(a)
        else:
            collapsed.add(a)
        x = collapsed.covering(v) or v
        shown = [x]
        while len(shown) < rows:
            if x in collapsed:
                x = last(x)
            x = nxt(x)
            if x is None:
                break
            shown.append(x)
        out.append(shown)
    return out


def tree_view_walk(tree, ops, rows):
    """Classical tree model: parent link, child list and next-sibling link per node, and a set of
    collapsed nodes. The visible row that contains v is its topmost collapsed ancestor (one climb
    to the root); the next row is the first child of an expanded node, otherwise the next sibling
    of the node or of its nearest ancestor that has one."""
    parent, kids, nsib = tree
    collapsed, out = set(), []
    for kind, a, b, v in ops:
        if kind == "insert":
            parent[b] = a
            ks = kids.setdefault(a, [])
            if ks:
                nsib[ks[-1]] = b
            ks.append(b)
        elif a in collapsed:
            collapsed.discard(a)
        else:
            collapsed.add(a)
        top, w = None, parent[v]
        while w is not None:
            if w in collapsed:
                top = w
            w = parent[w]
        x = top or v
        shown = [x]
        while len(shown) < rows:
            ks = kids.get(x)
            if ks and x not in collapsed:
                x = ks[0]
            else:
                while x is not None and x not in nsib:
                    x = parent[x]
                if x is None:
                    break
                x = nsib[x]
            shown.append(x)
        out.append(shown)
    return out


def classical_copy(t):
    parent, kids, nsib = {}, {}, {}
    for v in t.q1:
        parent[v] = t.get_parent(v)
        ks = t.children(v)
        if ks:
            kids[v] = ks
            nsib.update(zip(ks, ks[1:]))
    return parent, kids, nsib


def bench_tree_view(n, depths, steps, rows=20):
    print(f"\n### Use case: tree view with expand/collapse ({n:,} nodes, {steps:,} steps)\n")
    print("Each step changes the tree (inserts a leaf or collapses/expands a node, half and half), "
          f"then shows a random node: it finds the visible row that contains it and lists the {rows} "
          "visible rows from there. µs per step, best of three runs.\n")
    row("depth", "DTree [µs per step]", "parent walk [µs per step]", "factor")
    row("---:", "---:", "---:", "---:")
    for depth in depths:
        ops = tree_view_workload(n, depth, steps)
        t, _ = build_with_depth(n, depth)
        base = classical_copy(t)
        d = w = float("inf")
        for _ in range(3):
            t, _ = build_with_depth(n, depth)
            sec, a = timed(lambda o: tree_view_dtree(t, o, rows), ops)
            d = min(d, sec)
            tree = ({**base[0]}, {k: list(v) for k, v in base[1].items()}, {**base[2]})
            sec, b = timed(lambda o: tree_view_walk(tree, o, rows), ops)
            w = min(w, sec)
            assert a == b
        row(f"{depth:,}", f"{d / steps * 1e6:.1f}", f"{w / steps * 1e6:.1f}", factor(w, d))


# -- patterns from the review of DTree 1.8.0 -------------------------------------------------

def _chain(depth):
    t = DTree("R")
    t.insert("r", "c0")
    for i in range(1, depth):
        t.insert(f"c{i - 1}", f"c{i}")
    return t


def bench_review(depths, rounds, sibling_counts, members, unrelated):
    print("\n### Patterns from the review of DTree 1.8.0\n")
    print("Complexity patterns pointed out by Onur Safi. Each new child goes directly before its "
          "parent's closing cell, so none of them needs a search for the end of a subtree; in 1.8.0 "
          "the first two grew linearly with the depth.\n")
    row("pattern", "depth", "operations", "µs per operation")
    row("---", "---:", "---:", "---:")
    for depth in depths:
        # a deep branch is extended at the bottom, then a child is added near its top
        t = _chain(depth)
        bottom = f"c{depth - 1}"
        start = time.perf_counter()
        for r in range(rounds):
            t.insert(bottom, f"b{r}")
            bottom = f"b{r}"
            t.insert(f"c{r}", f"y{r}")
        dt = time.perf_counter() - start
        row("extend the bottom, then a child near the top (one round = 2 insertions)", f"{depth:,}",
            f"{rounds:,}", f"{dt / rounds * 1e6:.1f}")
    for depth in depths:
        t = _chain(depth)
        step = max(1, depth // rounds)
        targets = [f"c{i}" for i in range(0, depth, step)][:rounds]
        start = time.perf_counter()
        for i, s in enumerate(targets):
            t.insert_before(s, f"w{i}")                # s is the first child of its parent
        dt = time.perf_counter() - start
        row("insert_before a first child", f"{depth:,}", f"{len(targets):,}", f"{dt / len(targets) * 1e6:.1f}")

    print("\nNodes with many children: the position among the siblings is still found in the list of "
          "children, so these operations grow with the number of siblings.\n")
    row("pattern", "children", "operations", "µs per operation")
    row("---", "---:", "---:", "---:")
    for k in sibling_counts:
        t = DTree("S")
        t.insert("r", "p")
        for i in range(k):
            t.insert("p", f"k{i}")
        start = time.perf_counter()
        for i in range(k - 1, -1, -1):
            t.delete(f"k{i}")
        dt = time.perf_counter() - start
        row("delete the children, last to first", f"{k:,}", f"{k:,}", f"{dt / k * 1e6:.1f}")
        t = DTree("S")
        t.insert("r", "p")
        for i in range(k):
            t.insert("p", f"k{i}")
        ops = min(k, 2_000)
        start = time.perf_counter()
        for i in range(ops):
            t.insert_after(f"k{k - 1 - i % 10}", f"a{i}")
        dt = time.perf_counter() - start
        row("insert_after one of the last children", f"{k:,}", f"{ops:,}", f"{dt / ops * 1e6:.1f}")

    print("\nA constructed node is recomputed on its next use after any deletion or move in the tree, "
          "O(k log k) for k members, even if the change does not touch the set.\n")
    row("pattern", "members", "rounds", "ms per round")
    row("---", "---:", "---:", "---:")
    t, names, _ = build("random", 2 * members)
    vmin = t.vmin(names[1:members + 1])
    vmin.reaches_all(names[0])
    start = time.perf_counter()
    for r in range(unrelated):
        t.insert(names[-1], f"z{r}")
        t.delete(f"z{r}")
        vmin.reaches_all(names[0])
    dt = time.perf_counter() - start
    row("unrelated insert + delete, then a query", f"{members:,}", f"{unrelated:,}", f"{dt / unrelated * 1e3:.2f}")

    print("\nMemory, measured with tracemalloc (closing cells included).\n")
    row("structure", "nodes", "bytes per node")
    row("---", "---:", "---:")
    n = 100_000 if members >= 100_000 else 10_000
    for label, make in (("DTree, random tree", lambda: build("random", n)[0]),
                        ("DTree, chain", lambda: build("chain", n)[0]),
                        ("parent dictionary", lambda: {f"n{i}": f"n{i - 1}" for i in range(1, n)})):
        gc.collect()
        tracemalloc.start()
        obj = make()
        size = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        row(label, f"{n:,}", f"{size / n:,.0f}")
        del obj


# -- comparison with prior art -------------------------------------------------------------

def run_euler(steps):
    """Euler tour on one list, with node handles (insert returns the new node's handle)."""
    t, answers = EulerTour("E"), []
    nodes = [None] * (len(steps) + 1)
    for p, c, qs in steps:
        if c == 1:
            nodes[1] = t.insert("n0", "n1")
            nodes[0] = t.get_node("n0")
        else:
            nodes[c] = t.insert(nodes[p], f"n{c}")
        for u, v in qs:
            answers.append(t.can_reach(nodes[u], nodes[v]))
    return answers


def run_prepost(steps):
    """Pre/post numbers, recomputed lazily: only before a query that follows a change."""
    t, answers = PrePostNumbers(), []
    for p, c, qs in steps:
        t.insert(p, c)
        for u, v in qs:
            answers.append(t.can_reach(u, v))
    return answers


def batched_workload(n, depth, batch, seed=7):
    """Insertions as in dynamic_workload; after every `batch` insertions, `batch` queries
    between random nodes present at that moment (one query per insertion on average)."""
    rnd = random.Random(seed)
    steps = []
    for i in range(1, n):
        parent = i - 1 if i < depth else rnd.randrange(min(depth, i))
        qs = [(rnd.randrange(i + 1), rnd.randrange(i + 1)) for _ in range(batch)] if i % batch == 0 else []
        steps.append((parent, i, qs))
    return steps


def _build_euler(shape, n, seed=1):
    rnd = random.Random(seed)
    t, names = EulerTour("B"), ["n0"]
    pick = SHAPES[shape]
    start = time.perf_counter()
    for i in range(1, n):
        if shape == "star (inner node)" and i <= 2:
            parent = "n0"
        else:
            parent = pick(i, names, rnd)
        t.insert(parent, f"n{i}")
        names.append(f"n{i}")
    return t, time.perf_counter() - start


def bench_prior_art(n_build, n_dyn, depths, batches, set_n, set_depth, k, queries):
    print("\n### Comparison with prior art\n")
    print("Contenders: DTree (two lists, Q1 and Q2); the parenthesis (Euler-tour) encoding, every node "
          "an open and a close cell in one list, with the same rational positions (DList); pre/post "
          "numbers from a traversal, recomputed lazily, only before a query that follows a change; "
          "and the parent walk as before. All answers are checked against each other.\n")

    print(f"#### Building trees ({n_build:,} nodes)\n")
    row("shape", "DTree [s]", "Euler tour [s]", "renumberings DTree Q1 / Q2", "renumberings Euler tour")
    row("---", "---:", "---:", "---:", "---:")
    for shape in SHAPES:
        t, _, dt = build(shape, n_build)
        e, de = _build_euler(shape, n_build)
        row(shape, f"{dt:.2f}", f"{de:.2f}", f"{t.Q1.renumber_count:,} / {t.Q2.renumber_count:,}",
            f"{e.list.renumber_count:,}")

    print(f"\n#### Insertions with one query each ({n_dyn:,} nodes; µs per step, best of three runs)\n")
    row("depth", "DTree", "Euler tour", "parent walk")
    row("---:", "---:", "---:", "---:")
    for depth in depths:
        steps = dynamic_workload(n_dyn, depth, 1)
        d, a = best(run_dtree, steps)
        e, b = best(run_euler, steps)
        w, c = best(run_parent_walk, steps)
        assert a == b == c
        m = len(steps)
        row(f"{depth:,}", f"{d / m * 1e6:.2f}", f"{e / m * 1e6:.2f}", f"{w / m * 1e6:.2f}")

    depth = depths[len(depths) // 2]
    print(f"\n#### Insertions and queries in batches ({n_dyn:,} nodes, depth {depth:,}; µs per insertion "
          "with its share of the queries)\n")
    print("After every *b* insertions come *b* queries, so there is one query per insertion on "
          "average; pre/post numbers are recomputed once per batch.\n")
    row("batch b", "DTree", "Euler tour", "pre/post, lazy", "parent walk")
    row("---:", "---:", "---:", "---:", "---:")
    for b_ in batches:
        steps = batched_workload(n_dyn, depth, b_)
        d, a = best(run_dtree, steps)
        e, b = best(run_euler, steps)
        r, c = best(run_prepost, steps)
        w, x = best(run_parent_walk, steps)
        assert a == b == c == x
        m = len(steps)
        row(f"{b_:,}", f"{d / m * 1e6:.2f}", f"{e / m * 1e6:.2f}", f"{r / m * 1e6:.2f}", f"{w / m * 1e6:.2f}")

    print(f"\n#### And/or queries ({set_n:,} nodes, depth {set_depth:,}, set of {k:,} nodes, "
          f"{queries:,} query nodes; µs per query)\n")
    print("Each encoding answers with its own constructed points: DTree with VMin, VMax, UMin, UMax; "
          "the Euler tour with the minimum and maximum open and close positions over the set; pre/post "
          "numbers with the same over their numbers. The \"some\" questions use the members in order and "
          "one test in all three.\n")
    rnd = random.Random(4)
    parents = {}
    for i in range(1, set_n):
        parents[i] = i - 1 if i < set_depth else rnd.randrange(set_depth)
    t, e, pp = DTree("S"), EulerTour("S"), PrePostNumbers()
    for c, p in parents.items():
        t.insert(f"n{p}", f"n{c}")
        e.insert(f"n{p}", f"n{c}")
        pp.insert(p, c)
    S = rnd.sample(range(set_n), k)
    U = [rnd.randrange(set_n) for _ in range(queries)]
    Sn = [f"n{s}" for s in S]
    start = time.perf_counter()
    vmin, vmax, umin, umax = t.vmin(Sn), t.vmax(Sn), t.umin(Sn), t.umax(Sn)
    b_d = time.perf_counter() - start
    start = time.perf_counter()
    es = e.euler_set(Sn)
    b_e = time.perf_counter() - start
    start = time.perf_counter()
    ns = pp.number_set(S)
    b_p = time.perf_counter() - start
    th = [t.get_node(f"n{u}") for u in U]
    eh = [e.get_node(f"n{u}") for u in U]
    row("question", "DTree", "Euler tour", "pre/post")
    row("---", "---:", "---:", "---:")
    for name, fd, fe, fp in (
        ("reaches all", vmin.reaches_all, es.reaches_all, ns.reaches_all),
        ("reaches some", vmax.reaches_some, es.reaches_some, ns.reaches_some),
        ("reached by all", umax.reached_by_all, es.reached_by_all, ns.reached_by_all),
        ("reached by some", umin.reached_by_some, es.reached_by_some, ns.reached_by_some),
    ):
        cells = [name]
        results = []
        for f, xs in ((fd, th), (fe, eh), (fp, U)):
            start = time.perf_counter()
            results.append([f(x) for x in xs])
            cells.append(f"{(time.perf_counter() - start) / queries * 1e6:.2f}")
        assert results[0] == results[1] == results[2], name
        row(*cells)
    print(f"\n(Building the constructed points of {k:,} nodes: DTree, all four, {b_d * 1e3:.1f} ms; "
          f"Euler tour {b_e * 1e3:.1f} ms; pre/post {b_p * 1e3:.1f} ms.)")

    print("\n#### Memory, measured with tracemalloc\n")
    row("structure", "nodes", "bytes per node")
    row("---", "---:", "---:")
    m = n_build

    def make_pp():
        x = PrePostNumbers()
        for i in range(1, m):
            x.insert(random.Random(i).randrange(i), i)
        x.refresh()
        return x

    for label, make in (("DTree, random tree", lambda: build("random", m)[0]),
                        ("Euler tour, random tree", lambda: _build_euler("random", m)[0]),
                        ("pre/post numbers, random tree", make_pp)):
        gc.collect()
        tracemalloc.start()
        obj = make()
        size = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        row(label, f"{m:,}", f"{size / m:,.0f}")
        del obj

def _build_tour(make, shape, n, seed=1):
    """Build an Euler tour made by make(name) in the given shape."""
    rnd = random.Random(seed)
    t, names = make("B"), ["n0"]
    pick = SHAPES[shape]
    start = time.perf_counter()
    for i in range(1, n):
        parent = "n0" if shape == "star (inner node)" and i <= 2 else pick(i, names, rnd)
        t.insert(parent, f"n{i}")
        names.append(f"n{i}")
    return t, time.perf_counter() - start


def _grow_list(q, pattern, n, seed=3):
    """Insert n cells into q with a pattern, at the cell level (DList and IntList alike)."""
    rnd = random.Random(seed)
    cells = [q._insert_cell_after("a", q.first)]
    cells.append(q._insert_cell_after("b", cells[0]))
    left, right = cells                                           # the gap filled by "same gap"
    start = time.perf_counter()
    for i in range(n):
        if pattern == "append":
            a = q.last.prev
        elif pattern == "prepend":
            a = q.first
        elif pattern == "both ends, alternating":
            a = q.last.prev if i % 2 else q.first
        elif pattern == "one gap, from one side":
            a = left                                              # always directly after the same cell
        elif pattern == "one gap, alternating sides":
            a = left                                              # the newer half of the gap, alternately
        else:                                                     # hot spots
            a = rnd.choice([q.first, cells[len(cells) // 2], cells[-1], rnd.choice(cells)])
        c = q._insert_cell_after(f"v{i}", a)
        cells.append(c)
        if pattern == "one gap, alternating sides":
            if i % 2:
                left = c
            else:
                right = c
    return time.perf_counter() - start


def _tour_runner(make):
    """A runner like run_euler for any Euler tour made by make()."""
    def run(steps):
        t, answers = make(), []
        nodes = [None] * (len(steps) + 1)
        for p, c, qs in steps:
            if c == 1:
                nodes[1] = t.insert("n0", "n1")
                nodes[0] = t.get_node("n0")
            else:
                nodes[c] = t.insert(nodes[p], f"n{c}")
            for u, v in qs:
                answers.append(t.can_reach(nodes[u], nodes[v]))
        return answers
    return run


_POSITION_KINDS = (
    ("rational", lambda name: EulerTour(name), lambda: DList("L")),
    ("integer", lambda name: EulerTourInt(name), lambda: IntList("L")),
    ("float", lambda name: EulerTourNum(name, "float"), lambda: NumList("L", "float")),
    ("decimal", lambda name: EulerTourNum(name, "decimal"), lambda: NumList("L", "decimal")),
)


def bench_positions(n_build, n_dyn, depths):
    kinds = [k for k, _, _ in _POSITION_KINDS]
    print("\n### Kinds of positions\n")
    print("The same Euler tour on one list with four kinds of position: rational (DList: mediants, a "
          "region is renumbered when a denominator or numerator would exceed 2**61); integer, as in classical order "
          "maintenance (midpoints in [0, 2^62], a region is relabeled when no integer is left between two "
          "neighbors); and floating point, binary (float, as C#'s double) or decimal (28 significant "
          "digits, as C#'s decimal): midpoints, one unit beyond the neighbor next to SOURCE or SINK as with "
          "rationals, and a region is respaced when a midpoint is no longer representable. All renumber "
          "with the same density rule, so only the kind of position differs.\n")
    print(f"#### Building trees ({n_build:,} nodes): seconds, and renumberings\n")
    row("shape", *[f"{k} [s]" for k in kinds], *[f"renumberings {k}" for k in kinds])
    row("---", *["---:"] * (2 * len(kinds)))
    for shape in SHAPES:
        times, counts, ref = [], [], None
        for _, make, _ in _POSITION_KINDS:
            t, dt = _build_tour(make, shape, n_build)
            nodes = t.nodes()
            assert ref is None or nodes == ref
            ref = nodes
            times.append(f"{dt:.2f}")
            counts.append(f"{t.list.renumber_count:,}")
        row(shape, *times, *counts)

    print(f"\n#### Growing one list ({n_build:,} cells): seconds, and renumberings\n")
    row("pattern", *[f"{k} [s]" for k in kinds], *[f"renumberings {k}" for k in kinds])
    row("---", *["---:"] * (2 * len(kinds)))
    for pattern in ("append", "prepend", "both ends, alternating", "one gap, from one side",
                    "one gap, alternating sides", "hot spots"):
        times, counts, ref = [], [], None
        for _, _, make in _POSITION_KINDS:
            q = make()
            dt = _grow_list(q, pattern, n_build)
            assert ref is None or list(q) == ref
            ref = list(q)
            times.append(f"{dt:.2f}")
            counts.append(f"{q.renumber_count:,}")
        row(pattern, *times, *counts)

    print(f"\n#### Insertions with one query each ({n_dyn:,} nodes; µs per step, best of three runs)\n")
    row("depth", "DTree", *[f"Euler tour, {k}" for k in kinds])
    row("---:", *["---:"] * (1 + len(kinds)))
    for depth in depths:
        steps = dynamic_workload(n_dyn, depth, 1)
        d, a = best(run_dtree, steps)
        cells = [f"{depth:,}", f"{d / len(steps) * 1e6:.2f}"]
        for _, make, _ in _POSITION_KINDS:
            e, b = best(_tour_runner(lambda: make("E")), steps)
            assert a == b
            cells.append(f"{e / len(steps) * 1e6:.2f}")
        row(*cells)

    print(f"\n#### Queries on a built tree (random tree of {n_build:,} nodes, 1,000,000 random pairs of "
          "handles; µs per query)\n")
    rnd = random.Random(2)
    pairs = [(f"n{rnd.randrange(n_build)}", f"n{rnd.randrange(n_build)}") for _ in range(1_000_000)]
    row("encoding", "µs per query")
    row("---", "---:")
    results = []
    trees = [("DTree", build("random", n_build)[0])]
    trees += [(f"Euler tour, {k}", _build_tour(make, "random", n_build)[0]) for k, make, _ in _POSITION_KINDS]
    for label, tree in trees:
        hs = [(tree.get_node(u), tree.get_node(v)) for u, v in pairs]
        f = tree.can_reach
        start = time.perf_counter()
        results.append([f(u, v) for u, v in hs])
        row(label, f"{(time.perf_counter() - start) / len(hs) * 1e6:.3f}")
        del hs
    assert all(r == results[0] for r in results)

_RULES = (
    ("integer, midpoint", lambda name: EulerTourInt(name, 0), lambda: IntList("L", 0)),
    ("integer, MSD 2", lambda name: EulerTourInt(name, 2), lambda: IntList("L", 2)),
    ("integer, MSD 10", lambda name: EulerTourInt(name, 10), lambda: IntList("L", 10)),
    ("float, midpoint", lambda name: EulerTourNum(name, "float", 0), lambda: NumList("L", "float", 0)),
    ("float, MSD 2", lambda name: EulerTourNum(name, "float", 2), lambda: NumList("L", "float", 2)),
    ("float, MSD 10", lambda name: EulerTourNum(name, "float", 10), lambda: NumList("L", "float", 10)),
    ("decimal, midpoint", lambda name: EulerTourNum(name, "decimal", 0), lambda: NumList("L", "decimal", 0)),
    ("decimal, MSD 10", lambda name: EulerTourNum(name, "decimal", 10), lambda: NumList("L", "decimal", 10)),
)


def bench_rules(n_build, n_dyn, depths):
    names = [k for k, _, _ in _RULES]
    print("\n### Placement rules\n")
    print("Where a new position goes between two neighbors: the midpoint, or the left neighbor plus half "
          "the gap rounded at its most significant digit in base 2 or 10 (MSD), the rule of the original "
          "List.cs. Same Euler tour and density rule as above; rational positions always take the mediant.\n")
    print(f"#### Renumberings while building trees ({n_build:,} nodes)\n")
    row("shape", *names)
    row("---", *["---:"] * len(names))
    for shape in SHAPES:
        row(shape, *[f"{_build_tour(make, shape, n_build)[0].list.renumber_count:,}" for _, make, _ in _RULES])
    print(f"\n#### Renumberings while growing one list ({n_build:,} cells)\n")
    row("pattern", *names)
    row("---", *["---:"] * len(names))
    for pattern in ("append", "prepend", "both ends, alternating", "one gap, from one side",
                    "one gap, alternating sides", "hot spots"):
        cells = []
        for _, _, make in _RULES:
            q = make()
            _grow_list(q, pattern, n_build)
            cells.append(f"{q.renumber_count:,}")
        row(pattern, *cells)
    print(f"\n#### Insertions with one query each ({n_dyn:,} nodes; µs per step, best of three runs)\n")
    row("depth", *names)
    row("---:", *["---:"] * len(names))
    for depth in depths:
        steps = dynamic_workload(n_dyn, depth, 1)
        cells, ref = [f"{depth:,}"], None
        for _, make, _ in _RULES:
            sec, ans = best(_tour_runner(lambda: make("E")), steps)
            assert ref is None or ans == ref
            ref = ans
            cells.append(f"{sec / len(steps) * 1e6:.2f}")
        row(*cells)


_TREES = (
    ("DTree, rational", lambda name: DTree(name)),
    ("DTree, integer", lambda name: DTree(name, positions="integer")),
    ("EulerTree, rational", lambda name: EulerTree(name)),
    ("EulerTree, integer", lambda name: EulerTree(name, positions="integer")),
)


def _tree_runner(make):
    """Like run_dtree, for any tree made by make(name)."""
    def run(steps):
        t, answers = make("D"), []
        nodes = [None] * (len(steps) + 1)
        for p, c, qs in steps:
            if c == 1:
                nodes[1] = t.insert("n0", "n1")
                nodes[0] = t.get_node("n0")
            else:
                nodes[c] = t.insert(nodes[p], f"n{c}")
            for u, v in qs:
                answers.append(t.can_reach(nodes[u], nodes[v]))
        return answers
    return run


def bench_euler(n_build, n_dyn, depths, set_n, set_depth, k, queries):
    names = [n for n, _ in _TREES]
    print("\n### DTree and EulerTree\n")
    print("DTree keeps two lists, Q1 and Q2; EulerTree (triordinal.dtree.euler) keeps Q1 alone, with its "
          "closing cells, and decides reachability by whether a node lies inside another's block. Both "
          "with rational positions (the default) and with integer positions (positions=\"integer\").\n")
    print(f"#### Building trees ({n_build:,} nodes): seconds, and renumberings (summed over the lists)\n")
    row("shape", *[f"{x} [s]" for x in names], *[f"renumberings, {x}" for x in names])
    row("---", *["---:"] * (2 * len(names)))
    for shape in SHAPES:
        times, counts, ref = [], [], None
        for _, make in _TREES:
            rnd = random.Random(1)
            t, ns = make("B"), ["n0"]
            start = time.perf_counter()
            for i in range(1, n_build):
                parent = "n0" if shape == "star (inner node)" and i <= 2 else SHAPES[shape](i, ns, rnd)
                t.insert(parent, f"n{i}")
                ns.append(f"n{i}")
            times.append(f"{time.perf_counter() - start:.2f}")
            lists = [t._q1] + ([t._q2] if t._q2 is not None else [])
            counts.append(f"{sum(q.renumber_count for q in lists):,}")
            assert ref is None or t.q1 == ref
            ref = t.q1
        row(shape, *times, *counts)

    print(f"\n#### Insertions with one query each ({n_dyn:,} nodes; µs per step, best of three runs)\n")
    row("depth", *names)
    row("---:", *["---:"] * len(names))
    for depth in depths:
        steps = dynamic_workload(n_dyn, depth, 1)
        cells, ref = [f"{depth:,}"], None
        for _, make in _TREES:
            sec, ans = best(_tree_runner(make), steps)
            assert ref is None or ans == ref
            ref = ans
            cells.append(f"{sec / len(steps) * 1e6:.2f}")
        row(*cells)

    print(f"\n#### Queries ({set_n:,} nodes, depth {set_depth:,}; single pairs: 1,000,000 random pairs of "
          f"handles; and/or: a set of {k:,} nodes, {queries:,} query nodes; µs per query)\n")
    rnd = random.Random(4)
    parents = [None] + [i - 1 if i < set_depth else rnd.randrange(set_depth) for i in range(1, set_n)]
    S = [f"n{s}" for s in rnd.sample(range(set_n), k)]
    U = [f"n{rnd.randrange(set_n)}" for _ in range(queries)]
    pairs = [(f"n{rnd.randrange(set_n)}", f"n{rnd.randrange(set_n)}") for _ in range(1_000_000)]
    columns = {}
    for label, make in _TREES:
        t = make("S")
        for c in range(1, set_n):
            t.insert(f"n{parents[c]}", f"n{c}")
        hs = [(t.get_node(u), t.get_node(v)) for u, v in pairs]
        f = t.can_reach
        start = time.perf_counter()
        single = [f(u, v) for u, v in hs]
        col = {"single pairs": (time.perf_counter() - start) / len(hs), "_ans single pairs": single}
        del hs
        uh = [t.get_node(u) for u in U]
        vmin, vmax, umin, umax = t.vmin(S), t.vmax(S), t.umin(S), t.umax(S)
        for name, g in (("reaches all", vmin.reaches_all), ("reaches some", vmax.reaches_some),
                        ("reached by all", umax.reached_by_all), ("reached by some", umin.reached_by_some)):
            start = time.perf_counter()
            col["_ans " + name] = [g(u) for u in uh]
            col[name] = (time.perf_counter() - start) / queries
        columns[label] = col
    row("question", *names)
    row("---", *["---:"] * len(names))
    for q in ("single pairs", "reaches all", "reaches some", "reached by all", "reached by some"):
        answers = [columns[x]["_ans " + q] for x in names]
        assert all(a == answers[0] for a in answers), q
        row(q, *[f"{columns[x][q] * 1e6:.3f}" for x in names])

    print("\n#### Memory, measured with tracemalloc\n")
    row("structure", "nodes", "bytes per node")
    row("---", "---:", "---:")
    for label, make in _TREES:
        gc.collect()
        tracemalloc.start()
        rnd = random.Random(1)
        t = make("M")
        for i in range(1, n_build):
            t.insert(f"n{rnd.randrange(i)}", f"n{i}")
        size = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        row(label + ", random tree", f"{n_build:,}", f"{size / n_build:,.0f}")
        del t


def bench_moves(sizes, moves):
    """Random subtrees moved to random new parents (cut_n_paste), in DTree and EulerTree with both kinds
    of position. Legal moves are chosen with the tree's own can_reach (two comparisons), outside the
    timing; only the cut_n_paste calls are timed."""
    print(f"\n### Moving subtrees\n")
    print(f"A random tree is built, then {moves:,} times a random node (not the root) is moved with its "
          "subtree to a random new parent outside that subtree. Since 2.3.0 a moved subtree is placed "
          "as one block; a block that fits into its gap is a fitted paste, otherwise a region is "
          "renumbered. Counts are for the moves only, per list (Q1 / Q2).\n")
    row("tree", "positions", "nodes", "µs per move", "renumberings", "positions renumbered per move", "fitted pastes")
    row("---", "---", "---:", "---:", "---:", "---:", "---:")
    from triordinal.dtree.euler import EulerTree
    for kind, make in (("DTree", DTree), ("EulerTree", EulerTree)):
        for positions in ("rational", "integer"):
            for n in sizes:
                rnd = random.Random(9)
                t = make("M", positions=positions)
                for i in range(1, n):
                    t.insert(f"n{rnd.randrange(i)}", f"n{i}")
                handles = [t.get_node(f"n{i}") for i in range(n)]
                lists = [t.Q1] if kind == "EulerTree" else [t.Q1, t.Q2]
                count0 = [q.renumber_count for q in lists]
                moved0 = sum(q.renumber_moved for q in lists)
                paste0 = sum(getattr(q, "paste_count", 0) for q in lists)
                done, spent = 0, 0.0
                while done < moves:
                    u, p = handles[rnd.randrange(1, n)], handles[rnd.randrange(n)]
                    if u is p or t.can_reach(u, p):
                        continue                                    # p lies in u's subtree
                    start = time.perf_counter()
                    t.cut_n_paste(u, p)
                    spent += time.perf_counter() - start
                    done += 1
                counts = " / ".join(f"{q.renumber_count - c:,}" for q, c in zip(lists, count0))
                moved = (sum(q.renumber_moved for q in lists) - moved0) / moves
                pastes = sum(getattr(q, "paste_count", 0) for q in lists) - paste0
                row(kind, positions, f"{n:,}", f"{spent * 1e6 / moves:.2f}", counts, f"{moved:.1f}", f"{pastes:,}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sizes", nargs="*", type=int, help="tree sizes (default: 10000 100000)")
    ap.add_argument("--quick", action="store_true", help="small sizes for a fast check")
    ap.add_argument("--dynamic", action="store_true", help="only the dynamic updates and the tree view")
    ap.add_argument("--review", action="store_true", help="only the patterns from the review of 1.8.0")
    ap.add_argument("--prior-art", action="store_true", help="only the comparison with prior art")
    ap.add_argument("--euler", action="store_true", help="only DTree against EulerTree, by kind of position")
    ap.add_argument("--moves", action="store_true", help="only moving subtrees (cut_n_paste)")
    ap.add_argument("--note", default="", help="remark written into the report (e.g. machine state)")
    ap.add_argument("--no-save", action="store_true", help="do not write a Markdown report")
    args = ap.parse_args()
    started = datetime.datetime.now()
    tee = None
    if not args.no_save:
        tee = _Tee(sys.stdout)
        sys.stdout = tee
    try:
        run(args)
    finally:
        if tee is not None:
            sys.stdout = tee.console
            shown = " ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:])
            path = write_report(tee.copy.getvalue(), started, shown, args.note)
            print(f"\nReport written to {os.path.relpath(path, REPO)}")


def _moves(quick):
    if quick:
        bench_moves([2_000, 10_000], 2_000)
    else:
        bench_moves([10_000, 100_000], 20_000)


def run(args):
    if args.moves:
        print(f"DTree benchmarks, Python {sys.version.split()[0]}")
        _moves(args.quick)
        return
    if args.euler:
        print(f"DTree benchmarks, Python {sys.version.split()[0]}")
        _euler(args.quick)
        return
    if args.prior_art:
        print(f"DTree benchmarks, Python {sys.version.split()[0]}")
        _prior_art(args.quick)
        return
    if args.review:
        print(f"DTree benchmarks, Python {sys.version.split()[0]}")
        _review(args.quick)
        return
    if args.dynamic:
        print(f"DTree benchmarks, Python {sys.version.split()[0]}")
        if args.quick:
            bench_dynamic(5_000, [10, 100, 1_000], [500, 1_000, 2_000])
            bench_tree_view(5_000, [10, 100, 1_000], 1_000)
        else:
            bench_dynamic(20_000, [10, 100, 1_000, 10_000], [1_000, 2_000, 5_000])
            bench_tree_view(20_000, [10, 100, 1_000, 10_000], 5_000)
        return
    sizes = [1_000, 10_000] if args.quick else (args.sizes or [10_000, 100_000])
    print(f"DTree benchmarks, Python {sys.version.split()[0]}")
    bench_build(sizes)
    bench_lists(sizes)
    bench_operations(max(sizes), queries=100_000 if args.quick else 1_000_000)
    if args.quick:
        bench_depth(10_000, [10, 100, 1_000, 10_000], 20_000)
        bench_sets(10_000, [10, 100, 1_000], 100, 200)
        bench_dynamic(5_000, [10, 100, 1_000], [500, 1_000, 2_000])
        bench_tree_view(5_000, [10, 100, 1_000], 1_000)
    else:
        bench_depth(100_000, [10, 100, 1_000, 10_000, 100_000], 20_000)
        bench_sets(100_000, [10, 100, 1_000, 10_000], 1_000, 200)
        bench_dynamic(20_000, [10, 100, 1_000, 10_000], [1_000, 2_000, 5_000])
        bench_tree_view(20_000, [10, 100, 1_000, 10_000], 5_000)
    _review(args.quick)
    _prior_art(args.quick)
    _euler(args.quick)
    _moves(args.quick)


def _euler(quick):
    if quick:
        bench_euler(10_000, 5_000, [10, 1_000, 5_000], 10_000, 1_000, 100, 20_000)
    else:
        bench_euler(100_000, 20_000, [10, 1_000, 10_000], 100_000, 1_000, 1_000, 100_000)


def _prior_art(quick):
    if quick:
        bench_prior_art(10_000, 5_000, [10, 1_000, 5_000], [10, 100, 1_000], 10_000, 1_000, 100, 20_000)
        bench_positions(10_000, 5_000, [10, 1_000, 5_000])
        bench_rules(10_000, 5_000, [10, 1_000, 5_000])
    else:
        bench_prior_art(100_000, 20_000, [10, 1_000, 10_000], [10, 100, 1_000], 100_000, 1_000, 1_000, 100_000)
        bench_positions(100_000, 20_000, [10, 1_000, 10_000])
        bench_rules(100_000, 20_000, [10, 1_000, 10_000])


def _review(quick):
    if quick:
        bench_review([1_000, 2_000], 300, [2_000, 8_000], 10_000, 100)
    else:
        bench_review([2_000, 4_000, 8_000], 1_000, [10_000, 40_000], 100_000, 100)


if __name__ == "__main__":
    main()
