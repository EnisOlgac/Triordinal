"""Benchmark of DTree 3.0 against DTree 2.x (two lists) and EulerTree (Python).

    python -m triordinal.dtree.bench3 [--quick]

Every pattern runs on the three structures with the same operations; times are the best of three
runs, each after gc.collect(). Memory is measured with tracemalloc. DTree 3.0's climb_steps and
run_steps show how much a pattern made it look for delimiters and renew vertical runs.
"""

from __future__ import annotations

import gc
import random
import sys
import time
import tracemalloc

from triordinal.dlist import DList
from triordinal.dtree import DTree
from triordinal.dtree.euler import EulerTree
from triordinal.dtree.two_lists import DTree as DTree2

KINDS = (("DTree 2.x (two lists)", lambda: DTree2("B")), ("EulerTree", lambda: EulerTree("B")),
         ("DTree 3.0", lambda: DTree("B")))
NEW = "DTree 3.0"


def best(fn, runs=3):
    times, extra = [], None
    for _ in range(runs):
        gc.collect()
        t0 = time.perf_counter()
        extra = fn()
        times.append(time.perf_counter() - t0)
    return min(times), extra


def row(*cells):
    print("| " + " | ".join(str(c) for c in cells) + " |")


# -- tree shapes: a list of (parent, child) insertions, all appended as last kid ----------

def random_tree(n, seed=1):
    rnd = random.Random(seed)
    return [(f"n{rnd.randrange(i)}", f"n{i}") for i in range(1, n)]


def chain(n):
    return [(f"n{i - 1}", f"n{i}") for i in range(1, n)]


def star(n):
    return [("n0", f"n{i}") for i in range(1, n)]


def reading_order(n, seed=2, fan=4):
    """A document read top to bottom: each new node is appended as the last kid of a node on the
    current right edge (the path from the root to the last node), as a parser builds it."""
    rnd = random.Random(seed)
    edge, out = ["n0"], []
    for i in range(1, n):
        # go up a random number of levels (close elements), then open a new one
        up = min(len(edge) - 1, int(rnd.expovariate(1 / fan * 2)))
        del edge[len(edge) - up:]
        out.append((edge[-1], f"n{i}"))
        edge.append(f"n{i}")
    return out


def build(make, edges):
    t = make()
    for p, c in edges:
        t.insert(p, c)
    return t


# -- patterns ----------------------------------------------------------------------------------

def bench_build_and_query(n, queries):
    print(f"\n### Build ({n:,} nodes, each appended as the last kid) and {queries:,} random queries\n")
    row("shape", "structure", "build µs/insert", "query µs", "climb steps per query")
    row("---", "---", "---:", "---:", "---:")
    for shape, edges in (("random", random_tree(n)), ("chain", chain(n)), ("star", star(n)),
                         ("reading order", reading_order(n))):
        rnd = random.Random(9)
        pairs = [(f"n{rnd.randrange(n)}", f"n{rnd.randrange(n)}") for _ in range(queries)]
        for name, make in KINDS:
            tb, t = best(lambda: build(make, edges))
            hp = [(t.get_node(u), t.get_node(v)) for u, v in pairs]
            if name == NEW:
                t.climb_steps = t.run_steps = 0
            tq, _ = best(lambda: [t.can_reach(u, v) for u, v in hp])
            climbs = f"{t.climb_steps / (3 * queries):.1f}" if name == NEW else ""
            row(shape, name, f"{tb / (n - 1) * 1e6:.2f}", f"{tq / queries * 1e6:.3f}", climbs)


def which_step(t, u, v):
    """The step of DTree 3.0's cascade that decides can_reach(u, v) (1 to 5)."""
    lt = DList._lt
    if not lt(u.c, v.c):
        return 1
    if u.kh is None:
        return 2
    if u.h is None or u.h.next is not None:
        return 3
    last = u.kt.node
    if not lt(last.c, v.c) or last.kh is None:
        return 4
    return 5


def bench_cascade(n, queries):
    print(f"\n### The query cascade ({n:,} nodes, {queries:,} random queries)\n")
    print("Share of queries decided by each step: 1 v not right of u, 2 u has no kids, 3 u's right "
          "sibling (or the root), 4 u's last kid, 5 climb to the delimiter. For step 5: climb steps "
          "per climbing query, and the time of a query overall.\n")
    row("shape", "1", "2", "3", "4", "5", "steps per climb", "query µs")
    row("---", "---:", "---:", "---:", "---:", "---:", "---:", "---:")
    for shape, edges in (("random", random_tree(n)), ("chain", chain(n)), ("star", star(n)),
                         ("reading order", reading_order(n))):
        rnd = random.Random(9)
        pairs = [(f"n{rnd.randrange(n)}", f"n{rnd.randrange(n)}") for _ in range(queries)]
        for _ in (1,):
            t = build(lambda: DTree("B"), edges)
            hp = [(t.get_node(u), t.get_node(v)) for u, v in pairs]
            d = [0] * 6
            for u, v in hp:
                d[which_step(t, u, v)] += 1
            t.climb_steps = 0
            tq, _ = best(lambda: [t.can_reach(u, v) for u, v in hp])
            d = [x * 3 for x in d]
            total = sum(d)
            share = [f"{100 * d[i] / total:.1f}%" for i in range(1, 6)]
            per = f"{t.climb_steps / d[5]:,.1f}" if d[5] else "–"
            row(shape, *share, per, f"{tq / queries * 1e6:.3f}")


def bench_review(depth, rounds):
    print(f"\n### Review pattern: a chain of {depth:,}, extended at the bottom, then a child near the top\n")
    row("structure", "µs per round (2 insertions)", "climb steps per round")
    row("---", "---:", "---:")
    for name, make in KINDS:
        def run():
            t = build(make, chain(depth))
            if name == NEW:
                t.climb_steps = t.run_steps = 0
            bottom = f"n{depth - 1}"
            t0 = time.perf_counter()
            for r in range(rounds):
                t.insert(bottom, f"b{r}")
                bottom = f"b{r}"
                t.insert(f"n{r}", f"y{r}")
            return time.perf_counter() - t0, getattr(t, "climb_steps", 0) + getattr(t, "run_steps", 0)
        res = [run() for _ in range(3)]
        dt, climbs = min(res)
        row(name, f"{dt / rounds * 1e6:.1f}", f"{climbs / rounds:.0f}" if name == NEW else "")


def bench_append_mid(depth, count):
    print(f"\n### A chain of {depth:,}: {count:,} kids appended under its middle node\n")
    print("The middle node and all its ancestors are last kids: DTree 3.0 looks for the delimiter "
          "for every appended kid, through one vertical run.\n")
    row("structure", "µs per insertion", "climb steps per insertion")
    row("---", "---:", "---:")
    mid = f"n{depth // 2}"
    for name, make in KINDS:
        def run():
            t = build(make, chain(depth))
            if name == NEW:
                t.climb_steps = t.run_steps = 0
            t0 = time.perf_counter()
            for i in range(count):
                t.insert(mid, f"m{i}")
            return time.perf_counter() - t0, getattr(t, "climb_steps", 0) + getattr(t, "run_steps", 0)
        dt, climbs = min(run() for _ in range(3))
        row(name, f"{dt / count * 1e6:.1f}", f"{climbs / count:,.0f}" if name == NEW else "")


def bench_moves(n, moves):
    print(f"\n### {moves:,} random moves in a random tree of {n:,} nodes, a query after each\n")
    row("structure", "µs per move + query")
    row("---", "---:")
    edges = random_tree(n)
    rnd = random.Random(4)
    plan = [(f"n{rnd.randrange(1, n)}", f"n{rnd.randrange(n)}") for _ in range(moves)]
    for name, make in KINDS:
        def run():
            t = build(make, edges)
            t0, done = time.perf_counter(), 0
            for u, p in plan:
                if u == p or t.can_reach(u, p):
                    continue
                t.cut_n_paste(u, p)
                t.can_reach(p, u)
                done += 1
            return (time.perf_counter() - t0) / max(done, 1)
        row(name, f"{min(run() for _ in range(3)) * 1e6:.1f}")


def bench_memory(n):
    print(f"\n### Memory ({n:,} nodes, tracemalloc)\n")
    row("shape", "structure", "bytes per node")
    row("---", "---", "---:")
    for shape, edges in (("random", random_tree(n)), ("chain", chain(n))):
        for name, make in KINDS:
            gc.collect()
            tracemalloc.start()
            t = build(make, edges)
            size = tracemalloc.get_traced_memory()[0]
            tracemalloc.stop()
            row(shape, name, f"{size / n:,.0f}")
            del t


def main(argv=None):
    quick = "--quick" in (argv if argv is not None else sys.argv[1:])
    n = 10_000 if quick else 100_000
    bench_build_and_query(n, 20_000 if quick else 100_000)
    bench_cascade(n, 20_000 if quick else 100_000)
    bench_review(2_000 if quick else 20_000, 1_000 if quick else 5_000)
    bench_append_mid(2_000 if quick else 20_000, 1_000)
    bench_moves(5_000 if quick else 20_000, 2_000 if quick else 10_000)
    bench_memory(n)


if __name__ == "__main__":
    main()
