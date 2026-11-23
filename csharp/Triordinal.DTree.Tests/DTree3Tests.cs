// Tests and benchmark of DTree 3.0 (one projection, structure in the vertices), against a brute-force
// model; ported from the Python reference tests/test_dtree.py and triordinal/dtree/bench3.py.
// In this file DTree is DTree 3.0 (DirectedTrees.DTree); DTree 2.x is DirectedTrees.TwoLists.DTree.

using System.Diagnostics;
using Triordinal;
using Triordinal.DTree.Euler;

namespace DirectedTrees.Tests {

    /// <summary>Parent and ordered kids in plain lists.</summary>
    internal sealed class Model3 {
        internal readonly string Root;
        internal readonly Dictionary<string, string?> Up = new();
        internal readonly Dictionary<string, List<string>> Kids = new();

        internal Model3(string root) {
            Root = root;
            Up[root] = null;
            Kids[root] = new List<string>();
        }

        internal void Add(string p, string c, int i) {
            Up[c] = p;
            Kids[c] = new List<string>();
            Kids[p].Insert(i, c);
        }

        internal List<string> Preorder() {
            var outList = new List<string>();
            var stack = new Stack<string>();
            stack.Push(Root);
            while (stack.Count > 0) {
                var v = stack.Pop();
                outList.Add(v);
                for (int i = Kids[v].Count - 1; i >= 0; i--) stack.Push(Kids[v][i]);
            }
            return outList;
        }

        internal bool Reaches(string u, string v) {
            for (var x = Up[v]; x != null; x = Up[x]) if (x == u) return true;
            return false;
        }

        internal List<string> Subtree(string v) {
            var outList = new List<string>();
            var stack = new Stack<string>();
            stack.Push(v);
            while (stack.Count > 0) {
                var x = stack.Pop();
                outList.Add(x);
                for (int i = Kids[x].Count - 1; i >= 0; i--) stack.Push(Kids[x][i]);
            }
            return outList;
        }
    }

    internal static partial class Tests {
        private static void CheckV3(DTree t, Model3 m, Random rng, int queries = 300) {
            Program.Seq(t.Q1, m.Preorder(), "DTree 3.0: Q1 is the pre-order");
            var names = m.Up.Keys.ToList();
            for (int q = 0; q < queries; q++) {
                string u = names[rng.Next(names.Count)], v = names[rng.Next(names.Count)];
                Check(t.CanReach(u, v) == m.Reaches(u, v), $"DTree 3.0: CanReach({u}, {v})");
            }
            foreach (var v in names.OrderBy(_ => rng.Next()).Take(20)) {
                Program.Seq(t.Children(v), m.Kids[v], $"DTree 3.0: children of {v}");
                Check(t.GetParent(v) == m.Up[v], $"DTree 3.0: parent of {v}");
                Program.Seq(t.Subtree(v), m.Subtree(v), $"DTree 3.0: subtree of {v}");
            }
            // vertical runs: every member knows the top of its run of only kids
            var tops = new Dictionary<string, List<string>>();
            foreach (var v in names) {
                var x = v;
                while (m.Up[x] is string up && m.Kids[up].Count == 1) x = up;
                if (!tops.TryGetValue(x, out var list)) tops[x] = list = new List<string>();
                list.Add(v);
            }
            foreach (var (top, members) in tops) {
                var run = t.GetNode(top).R;
                if (members.Count == 1) { Check(run == null, $"DTree 3.0: {top} is a run of its own"); continue; }
                Check(run != null && run.Top.Name == top && run.Size == members.Count, $"DTree 3.0: run topped by {top}");
                foreach (var v in members) Check(t.GetNode(v).R == run, $"DTree 3.0: {v} in the run of {top}");
            }
            // constructed nodes, built for the query at hand
            for (int round = 0; round < 5; round++) {
                var s = names.OrderBy(_ => rng.Next()).Take(Math.Min(names.Count, rng.Next(1, 6))).ToList();
                var vmin = t.VMin(s); var vmax = t.VMax(s); var umin = t.UMin(s); var umax = t.UMax(s);
                foreach (var x in names.OrderBy(_ => rng.Next()).Take(10)) {
                    Check(vmin.ReachesAll(x) == s.All(y => m.Reaches(x, y)), $"DTree 3.0: VMin.ReachesAll({x})");
                    Check(vmax.ReachesSome(x) == s.Any(y => m.Reaches(x, y)), $"DTree 3.0: VMax.ReachesSome({x})");
                    Check(umax.ReachedByAll(x) == s.All(y => m.Reaches(y, x)), $"DTree 3.0: UMax.ReachedByAll({x})");
                    Check(umin.ReachedBySome(x) == s.Any(y => m.Reaches(y, x)), $"DTree 3.0: UMin.ReachedBySome({x})");
                    var cov = umin.Covering(x);
                    Check(cov == null || (s.Contains(cov) && m.Reaches(cov, x)), $"DTree 3.0: UMin.Covering({x})");
                }
            }
        }

        private static void RunRandomV3(Positions positions, int seed, int steps = 1500, bool deep = false) {
            var rng = new Random(seed);
            var t = new DTree("K", positions);
            var m = new Model3("r");
            t.Insert("r", "n0");
            m.Add("r", "n0", 0);
            int next = 1;
            for (int step = 0; step < steps; step++) {
                var names = m.Up.Keys.ToList();
                double op = rng.NextDouble();
                if (op < 0.55 || names.Count < 4) {
                    var p = deep && rng.NextDouble() < 0.7 ? names[^1] : names[rng.Next(names.Count)];
                    var c = $"n{next++}";
                    int how = rng.Next(4);
                    var kids = m.Kids[p];
                    if (how == 0 || kids.Count == 0) { t.Insert(p, c); m.Add(p, c, kids.Count); }
                    else if (how == 1) { t.InsertFirst(p, c); m.Add(p, c, 0); }
                    else {
                        var s = kids[rng.Next(kids.Count)];
                        int i = kids.IndexOf(s);
                        if (how == 2) { t.InsertBefore(s, c); m.Add(p, c, i); }
                        else { t.InsertAfter(s, c); m.Add(p, c, i + 1); }
                    }
                } else if (op < 0.7) {
                    var v = names[rng.Next(names.Count)];
                    if (v == "r") continue;
                    var p = m.Up[v]!;
                    int i = m.Kids[p].IndexOf(v);
                    m.Kids[p].RemoveAt(i);
                    m.Kids[p].InsertRange(i, m.Kids[v]);
                    foreach (var k in m.Kids[v]) m.Up[k] = p;
                    m.Up.Remove(v);
                    m.Kids.Remove(v);
                    t.Delete(v);
                } else if (op < 0.8) {
                    var v = names[rng.Next(names.Count)];
                    if (v == "r") continue;
                    var gone = m.Subtree(v);
                    m.Kids[m.Up[v]!].Remove(v);
                    foreach (var x in gone) { m.Up.Remove(x); m.Kids.Remove(x); }
                    Program.Seq(t.DeleteSubtree(v), gone, "DTree 3.0: DeleteSubtree");
                } else {
                    string u = names[rng.Next(names.Count)], p = names[rng.Next(names.Count)];
                    if (u == "r" || u == p || m.Reaches(u, p)) {
                        bool threw = false;
                        try { t.CutNPaste(u, p); } catch (InvalidOperationException) { threw = true; }
                        Check(threw, $"DTree 3.0: CutNPaste({u}, {p}) rejected");
                        continue;
                    }
                    m.Kids[m.Up[u]!].Remove(u);
                    m.Up[u] = p;
                    m.Kids[p].Add(u);
                    t.CutNPaste(u, p);
                }
                if (step % 50 == 0) CheckV3(t, m, rng);
            }
            CheckV3(t, m, rng, 2000);
            Check(t.Count == m.Up.Count, "DTree 3.0: Count");
        }

        public static void V3RandomRational() { for (int s = 0; s < 4; s++) RunRandomV3(Positions.Rational, s); }

        public static void V3RandomInteger() { for (int s = 0; s < 4; s++) RunRandomV3(Positions.Integer, s); }

        public static void V3Deep() {
            for (int s = 0; s < 3; s++) {
                RunRandomV3(Positions.Rational, 11 + s, deep: true);
                RunRandomV3(Positions.Integer, 21 + s, deep: true);
            }
        }

        public static void V3ChainIsOneRun() {
            var t = new DTree("C");
            t.Insert("r", "c0");
            for (int i = 1; i < 1000; i++) t.Insert($"c{i - 1}", $"c{i}");
            Check(t.ClimbSteps == 0, "DTree 3.0: building a chain looks for no delimiter");
            t.ClimbSteps = 0;
            Check(t.CanReach("c400", "c900"), "DTree 3.0: c400 reaches c900");
            Check(!t.CanReach("c400", "c300"), "DTree 3.0: c400 does not reach c300");
            Check(t.ClimbSteps <= 1, "DTree 3.0: one step to the top of the run");
            t.RunSteps = 0;
            t.Insert("c2", "x");                               // cut near the top: only r..c2 move
            Check(t.RunSteps < 10, $"DTree 3.0: a cut near the top is cheap ({t.RunSteps})");
            Check(t.GetNode("c500").R!.Top.Name == "c3", "DTree 3.0: the lower part is topped by c3");
            t.Delete("x");                                     // one kid again: the runs join
            Check(t.GetNode("c500").R!.Top.Name == "r", "DTree 3.0: the runs join again");
        }

        public static void V3ExamplesMatchTwoLists() {
            var dir = FindExamples();
            if (dir == null) { Console.WriteLine("     (examples folder not found, skipped)"); return; }
            foreach (var path in Directory.GetFiles(dir, "*.csx").OrderBy(p => p)) {
                var t = DTree.FromFile(path);
                var old = DirectedTrees.TwoLists.DTree.FromFile(path);
                Program.Seq(t.Q1, old.Q1, $"DTree 3.0: Q1 of {System.IO.Path.GetFileName(path)}");
                foreach (var u in t.Q1)
                    foreach (var v in t.Q1)
                        Check(t.CanReach(u, v) == old.CanReach(u, v), $"DTree 3.0: {System.IO.Path.GetFileName(path)}: {u} -> {v}");
            }
        }

        public static void V3Handles() {
            var t = new DTree("H");
            var a = t.Insert("r", "a");
            var b = t.Insert(a, "b");
            Check(t.CanReach(t.GetNode("r"), b), "DTree 3.0: handles: r reaches b");
            Check(a.Children.Count == 1 && a.Children[0] == b && b.Parent == a, "DTree 3.0: handles: parent and children");
            t.Delete(b);
            Check(!b.IsInTree, "DTree 3.0: a deleted handle is no longer in the tree");
            bool threw = false;
            try { t.CanReach(b, a); } catch (ArgumentException) { threw = true; }
            Check(threw, "DTree 3.0: a deleted handle is rejected");
        }

        public static void V3Errors() {
            var t = new DTree("E");
            Throws<ArgumentException>(() => t.Insert("r", "r"), "DTree 3.0: a root as its own child");
            t.Insert("r", "a");
            Throws<ArgumentException>(() => t.Insert("r", "a"), "DTree 3.0: a duplicate");
            Throws<KeyNotFoundException>(() => t.Insert("zz", "b"), "DTree 3.0: an unknown parent");
            Throws<InvalidOperationException>(() => t.InsertAfter("r", "b"), "DTree 3.0: a sibling of the root");
            Throws<InvalidOperationException>(() => t.Delete("r"), "DTree 3.0: deleting the root");
            Throws<InvalidOperationException>(() => t.CutNPaste("r", "a"), "DTree 3.0: moving the root");
            Throws<ArgumentException>(() => t.Insert("a", ""), "DTree 3.0: an empty name");
            Throws<ArgumentException>(() => t.AddLine("no operator"), "DTree 3.0: a line without operator");
            Throws<ArgumentException>(() => t.VMin(Array.Empty<string>()), "DTree 3.0: an empty constructed node");
        }
    }

    /// <summary>
    /// Benchmark of DTree 3.0 against DTree 2.x and EulerTree: dotnet run -c Release -- bench3 [quick].
    /// Every operation goes through node handles (cell access), not names: the trees are built with
    /// Insert(parent handle, name), queries and moves take handles. Each case is timed as a whole
    /// (best of three, after GC.Collect) and divided by its number of operations.
    /// </summary>
    internal static class Bench3 {
        private static void Row(params object[] cells) => Console.WriteLine("| " + string.Join(" | ", cells) + " |");

        private interface ITree {
            void Build((int P, int C)[] edges, string[] names);
            int Queries(int[] us, int[] vs);
            int Moves(int[] us, int[] ps);
            object Node(int i);
            object Insert(object parent, string child);
        }

        private sealed class V3 : ITree {
            private readonly DTree _t = new("B");
            private DNode[] _h = Array.Empty<DNode>();
            public void Build((int P, int C)[] edges, string[] names) {
                _h = new DNode[names.Length];
                _h[edges[0].C] = _t.Insert(names[edges[0].P], names[edges[0].C]);
                _h[edges[0].P] = _t.GetNode(names[edges[0].P]);
                for (int i = 1; i < edges.Length; i++) _h[edges[i].C] = _t.Insert(_h[edges[i].P], names[edges[i].C]);
            }
            public int Queries(int[] us, int[] vs) {
                int k = 0;
                for (int i = 0; i < us.Length; i++) if (_t.CanReach(_h[us[i]], _h[vs[i]])) k++;
                return k;
            }
            public int Moves(int[] us, int[] ps) {
                int done = 0;
                for (int i = 0; i < us.Length; i++) {
                    DNode u = _h[us[i]], p = _h[ps[i]];
                    if (u == p || _t.CanReach(u, p)) continue;
                    _t.CutNPaste(u, p);
                    _t.CanReach(p, u);
                    done++;
                }
                return done;
            }
            public object Node(int i) => _h[i];
            public object Insert(object parent, string child) => _t.Insert((DNode)parent, child);
        }

        private sealed class V2 : ITree {
            private readonly DirectedTrees.TwoLists.DTree _t;
            private DirectedTrees.TwoLists.DNode[] _h = Array.Empty<DirectedTrees.TwoLists.DNode>();
            internal V2(bool euler) { _t = euler ? new EulerTree("B") : new DirectedTrees.TwoLists.DTree("B"); }
            public void Build((int P, int C)[] edges, string[] names) {
                _h = new DirectedTrees.TwoLists.DNode[names.Length];
                _h[edges[0].C] = _t.Insert(names[edges[0].P], names[edges[0].C]);
                _h[edges[0].P] = _t.GetNode(names[edges[0].P]);
                for (int i = 1; i < edges.Length; i++) _h[edges[i].C] = _t.Insert(_h[edges[i].P], names[edges[i].C]);
            }
            public int Queries(int[] us, int[] vs) {
                int k = 0;
                for (int i = 0; i < us.Length; i++) if (_t.CanReach(_h[us[i]], _h[vs[i]])) k++;
                return k;
            }
            public int Moves(int[] us, int[] ps) {
                int done = 0;
                for (int i = 0; i < us.Length; i++) {
                    var u = _h[us[i]];
                    var p = _h[ps[i]];
                    if (u == p || _t.CanReach(u, p)) continue;
                    _t.CutNPaste(u, p);
                    _t.CanReach(p, u);
                    done++;
                }
                return done;
            }
            public object Node(int i) => _h[i];
            public object Insert(object parent, string child) => _t.Insert((DirectedTrees.TwoLists.DNode)parent, child);
        }

        private static readonly (string Name, Func<ITree> Make)[] Kinds = {
            ("DTree 2.x (two lists)", () => new V2(false)),
            ("EulerTree", () => new V2(true)),
            ("DTree 3.0", () => new V3()),
        };

        private static (int, int)[] RandomTree(int n, int seed = 1) {
            var rnd = new Random(seed);
            return Enumerable.Range(1, n - 1).Select(i => (rnd.Next(i), i)).ToArray();
        }

        private static (int, int)[] Chain(int n) => Enumerable.Range(1, n - 1).Select(i => (i - 1, i)).ToArray();

        private static (int, int)[] Star(int n) => Enumerable.Range(1, n - 1).Select(i => (0, i)).ToArray();

        /// <summary>A document read top to bottom: each new node is the last kid of a node on the right edge.</summary>
        private static (int, int)[] ReadingOrder(int n, int seed = 2) {
            var rnd = new Random(seed);
            var edge = new List<int> { 0 };
            var list = new List<(int, int)>();
            for (int i = 1; i < n; i++) {
                int up = Math.Min(edge.Count - 1, (int)(-Math.Log(1 - rnd.NextDouble()) * 2));
                edge.RemoveRange(edge.Count - up, up);
                list.Add((edge[^1], i));
                edge.Add(i);
            }
            return list.ToArray();
        }

        private static string[] Names(int n) => Enumerable.Range(0, n).Select(i => $"n{i}").ToArray();

        private static ITree Build(Func<ITree> make, (int, int)[] edges, string[] names) {
            var t = make();
            t.Build(edges, names);
            return t;
        }

        private static double Best(Func<double> run) {
            double best = double.MaxValue;
            for (int i = 0; i < 3; i++) {
                GC.Collect();
                GC.WaitForPendingFinalizers();
                best = Math.Min(best, run());
            }
            return best;
        }

        private static double Time(Action a) {
            var sw = Stopwatch.StartNew();
            a();
            return sw.Elapsed.TotalSeconds;
        }

        internal static void Run(string[] args) {
            bool quick = args.Contains("quick");
            int n = quick ? 10_000 : 100_000, queries = quick ? 100_000 : 1_000_000;
            var names = Names(n);
            Console.WriteLine($"## DTree 3.0 against DTree 2.x and EulerTree (C#, .NET {Environment.Version}; handles throughout)\n");

            Console.WriteLine($"### Build ({n:N0} nodes, each appended as the last kid) and {queries:N0} random queries\n");
            Row("shape", "structure", "build µs/insert", "query µs");
            Row("---", "---", "---:", "---:");
            foreach (var (shape, edges) in new[] { ("random", RandomTree(n)), ("chain", Chain(n)), ("star", Star(n)), ("reading order", ReadingOrder(n)) }) {
                var rnd = new Random(9);
                var us = new int[queries];
                var vs = new int[queries];
                for (int i = 0; i < queries; i++) { us[i] = rnd.Next(n); vs[i] = rnd.Next(n); }
                foreach (var (name, make) in Kinds) {
                    ITree t = null!;
                    double tb = Best(() => Time(() => t = Build(make, edges, names)));
                    int hits = 0;
                    double tq = Best(() => Time(() => hits = t.Queries(us, vs)));
                    Row(shape, name, $"{tb / (n - 1) * 1e6:F2}", $"{tq / queries * 1e6:F3}");
                    GC.KeepAlive(hits);
                }
            }

            int depth = quick ? 2_000 : 20_000, rounds = quick ? 1_000 : 5_000;
            var chainNames = Names(depth);
            var bNames = Enumerable.Range(0, rounds).Select(r => $"b{r}").ToArray();
            var yNames = Enumerable.Range(0, rounds).Select(r => $"y{r}").ToArray();
            var mNames = Enumerable.Range(0, 1000).Select(i => $"m{i}").ToArray();
            Console.WriteLine($"\n### Review pattern: a chain of {depth:N0}, extended at the bottom, then a child near the top\n");
            Row("structure", "µs per round (2 insertions)");
            Row("---", "---:");
            foreach (var (name, make) in Kinds) {
                double dt = Best(() => {
                    var t = Build(make, Chain(depth), chainNames);
                    var bottom = t.Node(depth - 1);
                    var near = Enumerable.Range(0, rounds).Select(t.Node).ToArray();
                    return Time(() => {
                        for (int r = 0; r < rounds; r++) {
                            bottom = t.Insert(bottom, bNames[r]);
                            t.Insert(near[r], yNames[r]);
                        }
                    });
                });
                Row(name, $"{dt / rounds * 1e6:F2}");
            }

            Console.WriteLine($"\n### A chain of {depth:N0}: 1,000 kids appended under its middle node\n");
            Row("structure", "µs per insertion");
            Row("---", "---:");
            foreach (var (name, make) in Kinds) {
                double dt = Best(() => {
                    var t = Build(make, Chain(depth), chainNames);
                    var mid = t.Node(depth / 2);
                    return Time(() => { for (int i = 0; i < 1000; i++) t.Insert(mid, mNames[i]); });
                });
                Row(name, $"{dt / 1000 * 1e6:F2}");
            }

            int mn = quick ? 5_000 : 20_000, moves = quick ? 2_000 : 10_000;
            Console.WriteLine($"\n### {moves:N0} random moves in a random tree of {mn:N0} nodes, a query after each\n");
            Row("structure", "µs per move + query");
            Row("---", "---:");
            var medges = RandomTree(mn);
            var mnames = Names(mn);
            var mr = new Random(4);
            var mus = new int[moves];
            var mps = new int[moves];
            for (int i = 0; i < moves; i++) { mus[i] = mr.Next(1, mn); mps[i] = mr.Next(mn); }
            foreach (var (name, make) in Kinds) {
                double dt = Best(() => {
                    var t = Build(make, medges, mnames);
                    int done = 0;
                    double s = Time(() => done = t.Moves(mus, mps));
                    return s / Math.Max(done, 1);
                });
                Row(name, $"{dt * 1e6:F2}");
            }

            Console.WriteLine($"\n### Memory ({n:N0} nodes, GC.GetTotalMemory; names allocated beforehand)\n");
            Row("shape", "structure", "bytes per node");
            Row("---", "---", "---:");
            foreach (var (shape, edges) in new[] { ("random", RandomTree(n)), ("chain", Chain(n)) }) {
                foreach (var (name, make) in Kinds) {
                    long before = GC.GetTotalMemory(true);
                    var t = Build(make, edges, names);
                    long after = GC.GetTotalMemory(true);
                    Row(shape, name, $"{(after - before) / (double)n:F0}");
                    GC.KeepAlive(t);
                }
            }
        }
    }
}
