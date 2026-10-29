"""Performance benchmarks for DTree.

Usage, after ``pip install triordinal-dtree`` (or from the repository's python/ folder,
where ``python benchmarks/bench.py`` does the same):

    python -m triordinal.dtree.bench                 # sizes 10,000 and 100,000
    python -m triordinal.dtree.bench 1000 1000000    # custom sizes
    python -m triordinal.dtree.bench --quick         # small sizes, a few seconds
    python -m triordinal.dtree.bench --dynamic       # only the dynamic updates and the tree view
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
nodes are inserted, collapsed and expanded while rows are shown.
Timings depend on the machine; the renumbering counts do not.
"""

import argparse
import datetime
import io
import os
import platform
import random
import sys
import time

import triordinal.dtree as _pkg
from triordinal.dtree import SINK, SOURCE, DList, DTree


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sizes", nargs="*", type=int, help="tree sizes (default: 10000 100000)")
    ap.add_argument("--quick", action="store_true", help="small sizes for a fast check")
    ap.add_argument("--dynamic", action="store_true", help="only the dynamic updates and the tree view")
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


def run(args):
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


if __name__ == "__main__":
    main()
