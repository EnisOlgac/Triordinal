// Tests and benchmarks for the C# DTree (port of the Python reference implementation).
//
//   dotnet run --project csharp/Triordinal.DTree.Tests -c Release            run all tests
//   dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench   run the benchmarks
//   dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench dynamic   only the dynamic updates and the tree view
//   ... -- bench --note "idle machine after restart"   remark for the report;  ... -- bench --no-save   no report
//
// Every benchmark run also writes its tables as a Markdown report to benchmarks/csharp/ at the
// repository root, named after date and time (e.g. 2026-10-17_14-18.md).
//
// Every query is checked against a brute-force parent/children model (no projections).

using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using DirectedTrees;
using Triordinal;

namespace DirectedTrees.Tests {

    internal static class Program {
        private static int _failures;
        private static int _checks;

        private static int Main(string[] args) {
            if (args.Length > 0 && args[0] == "bench") {
                Report.RunBench(args.Skip(1).ToArray());
                return 0;
            }
            var tests = new (string Name, Action Body)[] {
                ("readme usage", Tests.ReadmeUsage),
                ("insert rules", Tests.InsertRules),
                ("no self reachability", Tests.NoSelfReachability),
                ("two kinds of delete", Tests.TwoKindsOfDelete),
                ("delete root disallowed", Tests.DeleteRootDisallowed),
                ("cut into own subtree rejected", Tests.CutIntoOwnSubtreeRejected),
                ("list level access", Tests.ListLevelAccess),
                ("example files", Tests.ExampleFiles),
                ("DList operations (List.cs)", Tests.DListOperations),
                ("DList: markers cannot be inserted, moved or removed", Tests.DListMarkers),
                ("DList: many end insertions, then one gap (no overflow)", Tests.DListNoOverflow),
                ("random inserts vs reference", Tests.RandomInserts),
                ("random deletes and moves vs reference", Tests.RandomDeletesAndMoves),
                ("deep chain", Tests.DeepChain),
                ("wide node", Tests.WideNode),
                ("star needs no renumbering", Tests.StarNeedsNoRenumbering),
                ("alternating worst case", Tests.AlternatingWorstCase),
                ("growth at both ends", Tests.GrowthAtBothEnds),
                ("random list operations", Tests.RandomListOperations),
                ("node handles", Tests.NodeHandles),
                ("VMax: counterexample for reaches some", Tests.VMaxCounterexample),
                ("UMin: counterexample for reached by some", Tests.UMinCounterexample),
                ("UMin: nested members", Tests.UMinNestedMembers),
                ("constructed nodes: random sets vs brute force", Tests.ConstructedRandomSets),
                ("constructed nodes: incremental add", Tests.ConstructedIncrementalAdd),
                ("constructed nodes: empty set", Tests.ConstructedEmptySet),
                ("constructed nodes survive inserts, deletes and moves", Tests.ConstructedSurvivesChanges),
                ("constructed nodes: discard", Tests.ConstructedDiscard),
                ("next in Q1", Tests.NextInQ1),
                ("sibling insert: example and rules", Tests.SiblingInsertExample),
                ("sibling insert: description lines", Tests.SiblingInsertLines),
                ("sibling insert: random mix vs reference", Tests.SiblingInsertRandomMix),
                ("sibling insert: same gap many times", Tests.SiblingInsertSameGap),
                ("subtree end: top-down comb", Tests.SubtreeEndTopDownComb),
                ("subtree end: inserts mixed with deletes and moves", Tests.SubtreeEndMixed),
                ("subtree end: hint path always (budget 0)", Tests.SubtreeEndHintPathAlways),
            };
            var total = Stopwatch.StartNew();
            foreach (var (name, body) in tests) {
                int before = _failures;
                var sw = Stopwatch.StartNew();
                try {
                    body();
                } catch (Exception e) {
                    Fail($"unexpected {e.GetType().Name}: {e.Message}");
                }
                Console.WriteLine($"{(_failures == before ? "ok  " : "FAIL")} {name} ({sw.ElapsedMilliseconds} ms)");
            }
            Console.WriteLine($"\n{tests.Length} tests, {_checks:N0} checks, {_failures} failures, {total.Elapsed.TotalSeconds:F2} s");
            return _failures == 0 ? 0 : 1;
        }

        internal static void Check(bool condition, string message) {
            _checks++;
            if (!condition) Fail(message);
        }

        internal static void Seq<T>(IEnumerable<T> actual, IEnumerable<T> expected, string message) {
            var a = actual.ToList();
            var e = expected.ToList();
            Check(a.SequenceEqual(e), $"{message}: expected [{string.Join(", ", e)}], got [{string.Join(", ", a)}]");
        }

        internal static void Equal<T>(T actual, T expected, string message) =>
            Check(EqualityComparer<T>.Default.Equals(actual, expected), $"{message}: expected {expected}, got {actual}");

        internal static void Throws<TException>(Action action, string message) where TException : Exception {
            try {
                action();
            } catch (TException) {
                _checks++;
                return;
            }
            Fail($"{message}: expected {typeof(TException).Name}");
        }

        private static void Fail(string message) {
            _failures++;
            if (_failures <= 20) Console.WriteLine("     " + message);
        }
    }

    /// <summary>Plain parent/children model mirroring every operation.</summary>
    internal sealed class Reference {
        public readonly Dictionary<string, string> Parent = new();
        public readonly Dictionary<string, List<string>> Children = new();
        public string? Root;

        public void Insert(string u, string v) {
            Root ??= u;
            Parent[v] = u;
            Kids(u).Add(v);
        }

        public void Delete(string v) {
            var p = Parent[v];
            Parent.Remove(v);
            var kids = Children.TryGetValue(v, out var k) ? k : new List<string>();
            Children.Remove(v);
            var sib = Children[p];
            int i = sib.IndexOf(v);
            sib.RemoveAt(i);
            sib.InsertRange(i, kids);
            foreach (var c in kids) Parent[c] = p;
            if (sib.Count == 0) Children.Remove(p);
        }

        public void DeleteSubtree(string v) {
            var stack = new Stack<string>();
            stack.Push(v);
            var gone = new List<string>();
            while (stack.Count > 0) {
                var n = stack.Pop();
                gone.Add(n);
                if (Children.TryGetValue(n, out var kids)) {
                    foreach (var c in kids) stack.Push(c);
                    Children.Remove(n);
                }
            }
            var p = Parent[v];
            Children[p].Remove(v);
            if (Children[p].Count == 0) Children.Remove(p);
            foreach (var n in gone) Parent.Remove(n);
        }

        public void InsertAfter(string s, string v) {
            var p = Parent[s];
            var sib = Children[p];
            sib.Insert(sib.IndexOf(s) + 1, v);
            Parent[v] = p;
        }

        public void InsertBefore(string s, string v) {
            var p = Parent[s];
            var sib = Children[p];
            sib.Insert(sib.IndexOf(s), v);
            Parent[v] = p;
        }

        public void Move(string u, string p) {
            var old = Parent[u];
            Children[old].Remove(u);
            if (Children[old].Count == 0) Children.Remove(old);
            Parent[u] = p;
            Kids(p).Add(u);
        }

        public List<string> Nodes() {
            var list = new List<string> { Root! };
            list.AddRange(Parent.Keys);
            return list;
        }

        public List<string> Ancestors(string v) {   // [v, ..., root]
            var result = new List<string>();
            for (var w = v; ; w = Parent[w]) {
                result.Add(w);
                if (w == Root) break;
            }
            return result;
        }

        public List<string> Preorder(bool reverse) {
            var result = new List<string>();
            var stack = new Stack<string>();
            stack.Push(Root!);
            while (stack.Count > 0) {
                var n = stack.Pop();
                result.Add(n);
                if (!Children.TryGetValue(n, out var kids)) continue;
                IEnumerable<string> order = reverse ? kids : Enumerable.Reverse(kids);
                foreach (var c in order) stack.Push(c);
            }
            return result;
        }

        private List<string> Kids(string u) {
            if (!Children.TryGetValue(u, out var list)) {
                list = new List<string>();
                Children[u] = list;
            }
            return list;
        }
    }

    internal static partial class Tests {
        private static void Check(bool c, string m) => Program.Check(c, m);
        private static void Seq<T>(IEnumerable<T> a, IEnumerable<T> e, string m) => Program.Seq(a, e, m);
        private static void Equal<T>(T a, T e, string m) => Program.Equal(a, e, m);
        private static void Throws<TEx>(Action a, string m) where TEx : Exception => Program.Throws<TEx>(a, m);

        private static void CheckAgainst(DTree t, Reference r, Random rnd) {
            Check(t.Q1.PositionsStrictlyIncrease(), "Q1 positions increase");
            Check(t.Q2.PositionsStrictlyIncrease(), "Q2 positions increase");
            var nodes = r.Nodes();
            Equal(t.Size, nodes.Count, "size");
            Equal(t.Root, r.Root, "root");
            Seq(t.Q1.ToList(), r.Preorder(false), "Q1");
            Seq(t.Q2.ToList(), r.Preorder(true), "Q2");
            foreach (var v in nodes) {
                var anc = r.Ancestors(v);
                Seq(t.PathToRoot(v), anc, $"PathToRoot({v})");
                Equal(t.Depth(v), anc.Count - 1, $"Depth({v})");
                Equal(t.GetParent(v), r.Parent.TryGetValue(v, out var p) ? p : null, $"GetParent({v})");
                Equal(t.IsLeaf(v), !r.Children.ContainsKey(v), $"IsLeaf({v})");
            }
            var sample = nodes.Count <= 40 ? nodes : nodes.OrderBy(_ => rnd.Next()).Take(40).ToList();
            foreach (var u in sample)
                foreach (var v in sample) {
                    bool expected = u != v && r.Ancestors(v).Contains(u);
                    Equal(t.CanReach(u, v), expected, $"CanReach({u}, {v})");
                    Equal(t.IsAncestor(u, v), expected, $"IsAncestor({u}, {v})");
                    Equal(t.IsDescendant(v, u), expected, $"IsDescendant({v}, {u})");
                    Equal(t.CanReach(t.GetNode(u), t.GetNode(v)), expected, $"CanReach(handle {u}, handle {v})");
                }
        }

        private static (DTree, Reference, Random) RandomTree(int n, int seed) {
            var rnd = new Random(seed);
            var t = new DTree("R");
            var r = new Reference();
            var names = new List<string> { "n0" };
            for (int i = 1; i < n; i++) {
                var p = names[rnd.Next(names.Count)];
                t.Insert(p, $"n{i}");
                r.Insert(p, $"n{i}");
                names.Add($"n{i}");
            }
            return (t, r, rnd);
        }

        public static void ReadmeUsage() {
            var t = new DTree("P1");
            t.Insert("A", "B");
            t.Insert("B", "C");
            Check(t.CanReach("A", "C"), "A reaches C");
            Seq(t.PathToRoot("C"), new[] { "C", "B", "A" }, "PathToRoot");
            Seq(t.RootToPath("C"), new[] { "A", "B", "C" }, "RootToPath");
            Equal(t.Root, "A", "Root");
            Equal(t.GetParent("A"), null, "GetParent(root)");
            Equal(t.Depth("A"), 0, "Depth(root)");
            Equal(t.Source, Marker.Source, "Source");
            Equal(t.Sink, Marker.Sink, "Sink");
        }

        public static void InsertRules() {
            var t = new DTree();
            t.Insert("A", "B");
            Throws<KeyNotFoundException>(() => t.Insert("X", "Y"), "parent must exist");
            Throws<ArgumentException>(() => t.Insert("A", "B"), "child must not exist");
        }

        public static void NoSelfReachability() {
            var t = new DTree();
            t.Insert("A", "B");
            foreach (var v in new[] { "A", "B" }) {
                Check(!t.CanReach(v, v), $"CanReach({v},{v}) is false");
                Check(t.CanNotReach(v, v), $"CanNotReach({v},{v})");
                Check(!t.IsAncestor(v, v), $"IsAncestor({v},{v}) is false");
            }
            Seq(t.Subtree("A"), new[] { "A", "B" }, "Subtree(A)");
            Seq(t.Path("A", "A"), new[] { "A" }, "Path(A,A)");
            Throws<InvalidOperationException>(() => t.CutNPaste("B", "B"), "CutNPaste(B,B)");
        }

        public static void TwoKindsOfDelete() {
            static DTree Build() {
                var t = new DTree();
                foreach (var (u, v) in new[] { ("A", "B"), ("B", "C"), ("B", "D"), ("A", "E") }) t.Insert(u, v);
                return t;
            }
            var t1 = Build();
            t1.Delete("B");
            Seq(t1.Children("A"), new[] { "C", "D", "E" }, "children after Delete");
            Seq(t1.Q1.ToList(), new[] { "A", "C", "D", "E" }, "Q1 after Delete");
            var t2 = Build();
            Seq(t2.DeleteSubtree("B"), new[] { "B", "C", "D" }, "DeleteSubtree result");
            Seq(t2.Q1.ToList(), new[] { "A", "E" }, "Q1 after DeleteSubtree");
            Seq(t2.Q2.ToList(), new[] { "A", "E" }, "Q2 after DeleteSubtree");
            Throws<InvalidOperationException>(() => t2.DeleteSubtree("A"), "DeleteSubtree(root)");
        }

        public static void DeleteRootDisallowed() {
            var t = new DTree();
            t.Insert("A", "B");
            Throws<InvalidOperationException>(() => t.Delete("A"), "Delete(root)");
        }

        public static void CutIntoOwnSubtreeRejected() {
            var t = new DTree();
            t.Insert("A", "B");
            t.Insert("B", "C");
            Throws<InvalidOperationException>(() => t.CutNPaste("B", "C"), "CutNPaste into own subtree");
        }

        public static void ListLevelAccess() {
            var t = new DTree();
            t.Insert("A", "B");
            t.Insert("A", "C");
            Check(t.Q1.IsLeftOf("B", "C"), "B left of C in Q1");
            Check(t.Q2.IsLeftOf("C", "B"), "C left of B in Q2");
        }

        public static void ExampleFiles() {
            var dir = FindExamples();
            if (dir == null) { Console.WriteLine("     (examples folder not found, skipped)"); return; }
            foreach (var name in new[] { "Test.csx", "Test1.csx", "test23.csx" }) {
                var path = System.IO.Path.Combine(dir, name);
                if (!File.Exists(path)) continue;
                var t = DTree.FromFile(path);
                Equal(t.Root, "01", $"{name}: root");
                Check(t.CanReach("01", "22"), $"{name}: 01 reaches 22");
                Seq(t.PathToRoot("22"), new[] { "22", "10", "06", "04", "01" }, $"{name}: PathToRoot(22)");
            }
            var sib = System.IO.Path.Combine(dir, "siblings.csx");
            if (File.Exists(sib)) {
                var t = DTree.FromFile(sib);
                Seq(t.Children("01"), new[] { "02", "04", "06", "05" }, "siblings.csx: children of 01");
                Seq(t.Q1.ToList(), new[] { "01", "02", "03a", "03", "04", "06", "05" }, "siblings.csx: Q1");
                Seq(t.Q2.ToList(), new[] { "01", "05", "06", "04", "02", "03", "03a" }, "siblings.csx: Q2");
            }
        }

        private static string? FindExamples() {
            for (var d = new DirectoryInfo(AppContext.BaseDirectory); d != null; d = d.Parent) {
                var candidate = System.IO.Path.Combine(d.FullName, "examples");
                if (Directory.Exists(candidate)) return candidate;
            }
            return null;
        }

        public static void DListOperations() {
            var q = new DList("Q");
            Equal(q.Source, Marker.Source, "Source");
            Equal(q.Sink, Marker.Sink, "Sink");
            q.InsertBefore("a", Marker.Sink);
            q.InsertAfter("c", "a");
            q.InsertBefore("b", "c");
            Seq(q.ToList(), new[] { "a", "b", "c" }, "order");
            Seq(q.ToList(true), new[] { Marker.Source, "a", "b", "c", Marker.Sink }, "with markers");
            Check(q.IsLeftOf("a", "c") && q.IsRightOf("c", "a"), "left/right");
            Check(q.IsSelfOrLeftOf("b", "b") && q.IsSelfOrRightOf("b", "b"), "self-or");
            Check(!q.IsLeftOf("b", "b"), "strict");
            Equal(q.Prev("b"), "a", "Prev");
            Equal(q.Next("b"), "c", "Next");
            Check(q.IsAllocated("a") && q.IsNotAllocated("z"), "allocated");
            Check(q.Index("z") == null, "Index of absent node");
            q.InsertBefore("d", Marker.Source);   // redirected to after SOURCE
            q.InsertAfter("e", Marker.Sink);      // redirected to before SINK
            Seq(q.ToList(), new[] { "d", "a", "b", "c", "e" }, "marker redirects");
            q.InsertAfter("a", "a");              // no-op
            q.InsertAfter("b", "a");              // already there: no-op
            q.InsertAfter("d", "c");              // existing node is moved
            Seq(q.ToList(), new[] { "a", "b", "c", "d", "e" }, "move");
            var r = new DList("R");
            foreach (var n in new[] { "a", "b", "c", "d", "e" }) r.InsertBefore(n, Marker.Sink);
            Check(q.IsSameAs(r), "IsSameAs");
            r.Remove("c");
            Check(!q.IsSameAs(r), "not IsSameAs");
        }

        public static void DListMarkers() {
            var q = new DList("Q");
            q.InsertAfter("a", Marker.Source);
            Throws<ArgumentException>(() => q.InsertBefore(Marker.Sink, "a"), "InsertBefore(SINK, a)");
            Throws<ArgumentException>(() => q.InsertAfter(Marker.Source, "a"), "InsertAfter(SOURCE, a)");
            Throws<ArgumentException>(() => q.InsertAfter(Marker.Sink, "a"), "InsertAfter(SINK, a)");
            Throws<ArgumentException>(() => q.InsertBefore(Marker.Source, "a"), "InsertBefore(SOURCE, a)");
            Throws<InvalidOperationException>(() => q.Remove(Marker.Source), "Remove(SOURCE)");
            Seq(q.ToList(true), new[] { Marker.Source, "a", Marker.Sink }, "list intact");
        }

        public static void DListNoOverflow() {
            // The reviewer's pattern: a child is added at the end and the previous one deleted,
            // 6 million times, so the values at the end grow by one each time; then one gap is
            // filled alternately until its denominators approach 2^40. Before 2.0.0 this
            // overflowed 64-bit numerators and left the list unsorted.
            var q = new DList("Q");
            q.InsertAfter("r", Marker.Source);
            string? prev = null;
            for (int i = 0; i < 6_000_000; i++) {
                var name = "c" + i;
                q.InsertBefore(name, Marker.Sink);
                if (prev != null) q.Remove(prev);
                prev = name;
            }
            var reference = new List<string> { "r", prev! };
            string left = "r", right = prev!;
            for (int i = 0; i < 300; i++) {
                var name = "s" + i;
                q.InsertAfter(name, left);
                reference.Insert(reference.IndexOf(left) + 1, name);
                if (i % 2 == 0) right = name; else left = name;
            }
            Seq(q.ToList(), reference.ToArray(), "order after many insertions");
            for (int i = 1; i < reference.Count; i++)
                Check(q.Precedes(reference[i - 1], reference[i]), "positions increase along the list");
        }

        public static void RandomInserts() {
            for (int seed = 0; seed < 30; seed++) {
                var (t, r, rnd) = RandomTree(60, seed);
                CheckAgainst(t, r, rnd);
            }
        }

        public static void RandomDeletesAndMoves() {
            for (int seed = 0; seed < 30; seed++) {
                var (t, r, rnd) = RandomTree(80, seed);
                for (int step = 0; step < 40; step++) {
                    var nodes = r.Nodes().Where(n => n != r.Root).ToList();
                    if (nodes.Count < 10) break;
                    double x = rnd.NextDouble();
                    if (x < 0.35) {
                        var v = nodes[rnd.Next(nodes.Count)];
                        t.Delete(v);
                        r.Delete(v);
                    } else if (x < 0.5) {
                        var v = nodes[rnd.Next(nodes.Count)];
                        var expected = t.Subtree(v);
                        Seq(t.DeleteSubtree(v), expected, "DeleteSubtree result");
                        r.DeleteSubtree(v);
                        foreach (var n in expected) Check(!t.Contains(n), $"{n} removed");
                    } else {
                        var u = nodes[rnd.Next(nodes.Count)];
                        var banned = new HashSet<string>(t.Subtree(u));
                        var targets = r.Nodes().Where(n => !banned.Contains(n)).ToList();
                        var p = targets[rnd.Next(targets.Count)];
                        t.CutNPaste(u, p);
                        r.Move(u, p);
                    }
                    CheckAgainst(t, r, rnd);
                }
            }
        }

        public static void DeepChain() {
            var t = new DTree();
            for (int i = 0; i < 5000; i++) t.Insert($"v{i}", $"v{i + 1}");
            Equal(t.Depth("v5000"), 5000, "depth");
            Check(t.CanReach("v0", "v5000"), "top reaches bottom");
            Check(!t.CanReach("v5000", "v0"), "bottom does not reach top");
            Equal((t.Q1.RenumberCount, t.Q2.RenumberCount), (0L, 0L), "no renumbering for a chain");
        }

        public static void WideNode() {
            var t = new DTree();
            for (int i = 0; i < 5000; i++) t.Insert("r", $"c{i}");
            Equal(t.SubtreeSize("r"), 5001, "subtree size");
            Check(!t.CanReach("c1", "c2"), "siblings unconnected");
            Seq(t.Q2.ToList().Take(3), new[] { "r", "c4999", "c4998" }, "Q2 start");
            Check(t.Q2.PositionsStrictlyIncrease(), "Q2 positions increase");
        }

        public static void StarNeedsNoRenumbering() {
            var t = new DTree();
            t.Insert("r", "x");
            t.Insert("r", "y");
            for (int i = 0; i < 5000; i++) t.Insert("x", $"c{i}");
            Equal((t.Q1.RenumberCount, t.Q2.RenumberCount), (0L, 0L), "no renumbering for a star");
            Check(t.CanReach("x", "c4999"), "x reaches c4999");
            Check(!t.CanReach("c0", "c1"), "siblings unconnected");
        }

        public static void AlternatingWorstCase() {
            var t = new DTree();
            var left = "n0";
            for (int i = 1; i < 4000; i++) {
                t.Insert(left, $"n{i}");
                if (i % 2 == 0) left = $"n{i}";
            }
            Check(t.Q2.RenumberCount > 0, "alternating insertions force renumbering");
            Check(t.Q1.PositionsStrictlyIncrease(), "Q1 positions increase");
            Check(t.Q2.PositionsStrictlyIncrease(), "Q2 positions increase");
            Check(t.Q1.MaxDenominator() <= 1L << 40 && t.Q2.MaxDenominator() <= 1L << 40, "denominators bounded");
        }

        public static void GrowthAtBothEnds() {
            var q = new DList("Q");
            for (int i = 0; i < 5000; i++) {
                q.InsertBefore($"r{i}", Marker.Sink);
                q.InsertAfter($"l{i}", Marker.Source);
            }
            Check(q.PositionsStrictlyIncrease(), "positions increase");
            Seq(q.ToList().Take(2), new[] { "l4999", "l4998" }, "left end");
            Seq(q.ToList().TakeLast(2), new[] { "r4998", "r4999" }, "right end");
            Equal(q.RenumberCount, 0L, "no renumbering");
        }

        public static void RandomListOperations() {
            var rnd = new Random(7);
            var q = new DList("Q");
            var reference = new List<string>();
            for (int i = 0; i < 20000; i++) {
                double x = rnd.NextDouble();
                if (reference.Count > 0 && x < 0.15) {
                    var v = reference[rnd.Next(reference.Count)];
                    q.Remove(v);
                    reference.Remove(v);
                    continue;
                }
                var name = $"v{i}";
                if (reference.Count == 0 || x < 0.25) {
                    q.InsertAfter(name, Marker.Source);
                    reference.Insert(0, name);
                } else {
                    // hammer a few hot spots to force renumbering
                    int[] spots = { 0, reference.Count / 2, reference.Count - 1, rnd.Next(reference.Count) };
                    int j = spots[rnd.Next(spots.Length)];
                    if (rnd.NextDouble() < 0.5) {
                        q.InsertAfter(name, reference[j]);
                        reference.Insert(j + 1, name);
                    } else {
                        q.InsertBefore(name, reference[j]);
                        reference.Insert(j, name);
                    }
                }
            }
            Seq(q.ToList(), reference, "order matches a plain list");
            Check(q.PositionsStrictlyIncrease(), "positions increase");
        }
    }

    internal static partial class Tests {
        public static void NodeHandles() {
            var t = new DTree();
            var b = t.Insert("A", "B");
            var c = t.Insert(b, "C");
            var d = t.Insert("A", "D");
            var a = t.GetNode("A");
            Equal(b.Name, "B", "Insert returns the child's handle");
            Check(t.CanReach(a, c) && t.CanReach(b, c), "handles: ancestors reach C");
            Check(!t.CanReach(c, a) && !t.CanReach(b, d) && !t.CanReach(c, c), "handles: no other reachability");
            Check(t.IsRoot(a) && !t.IsRoot(b), "IsRoot on handles");
            Equal(t.Depth(c), 2, "Depth on handle");
            Check(c.Parent == b && a.Parent == null, "Parent on handles");
            Seq(a.Children.Select(n => n.Name), new[] { "B", "D" }, "Children on handle");
            Check(t.TryGetNode("D", out var d2) && d2 == d && !t.TryGetNode("X", out _), "TryGetNode");
            t.CutNPaste(c, d);
            Check(t.CanReach(d, c) && !t.CanReach(b, c), "CutNPaste on handles");
            t.Delete(b);
            Check(!b.IsInTree && !t.CanReach(a, b), "deleted handle no longer reaches or is reached");
            Throws<ArgumentException>(() => t.Insert(b, "E"), "Insert under a deleted handle");
            var other = new DTree("other");
            var x = other.Insert("X", "Y");
            Check(!t.CanReach(a, x), "handles of another tree are not reachable");
            Throws<ArgumentException>(() => t.Delete(x), "Delete with a handle of another tree");
            Equal(t.DeleteSubtree(d).Count, 2, "DeleteSubtree on handle removes D and C");
            Check(!c.IsInTree && t.Size == 1, "only the root is left");
        }
    }

    internal static partial class Tests {
        private static bool BruteReaches(Reference r, string u, string v) => u != v && r.Ancestors(v).Contains(u);

        private sealed record ConstructedNodes(VMin VMin, VMax VMax, UMin UMin, UMax UMax) {
            public static ConstructedNodes Of(DTree t, IEnumerable<string> set) {
                var list = set.ToList();
                return new(t.VMin(list), t.VMax(list.Select(t.GetNode)), t.UMin(list), t.UMax(list.Select(t.GetNode)));
            }
        }

        private static void CheckConstructed(DTree t, Reference r, ConstructedNodes c, List<string> set, string tag) {
            foreach (var u in r.Nodes()) {
                bool all = set.All(v => BruteReaches(r, u, v));
                bool some = set.Any(v => BruteReaches(r, u, v));
                bool byAll = set.All(v => BruteReaches(r, v, u));
                bool bySome = set.Any(v => BruteReaches(r, v, u));
                var h = t.GetNode(u);
                Equal(c.VMin.ReachesAll(u), all, $"{tag}: VMin.ReachesAll({u})");
                Equal(c.VMax.ReachesSome(u), some, $"{tag}: VMax.ReachesSome({u})");
                Equal(c.VMax.ReachesSome(h), some, $"{tag}: VMax.ReachesSome(handle {u})");
                Equal(c.UMax.ReachedByAll(u), byAll, $"{tag}: UMax.ReachedByAll({u})");
                Equal(c.UMin.ReachedBySome(u), bySome, $"{tag}: UMin.ReachedBySome({u})");
                Equal(c.UMin.ReachedBySome(h), bySome, $"{tag}: UMin.ReachedBySome(handle {u})");
                if (some) Check(c.VMax.MayReachSome(u), $"{tag}: MayReachSome({u}) must not reject a true case");
                if (bySome) Check(c.UMin.MayBeReachedBySome(u), $"{tag}: MayBeReachedBySome({u}) must not reject a true case");
            }
        }

        private static (DTree, Reference) Build(params (string, string)[] edges) {
            var t = new DTree();
            var r = new Reference();
            foreach (var (u, v) in edges) {
                t.Insert(u, v);
                r.Insert(u, v);
            }
            return (t, r);
        }

        public static void VMaxCounterexample() {
            var (t, r) = Build(("r", "n1"), ("n1", "n2"), ("r", "n3"), ("n2", "n4"), ("n4", "n5"), ("n3", "n6"), ("n3", "n7"));
            var set = new List<string> { "n1", "n7" };
            var vmax = t.VMax(set);
            Equal(vmax.IndexNodes, ("n7", "n1"), "VMax index nodes (Q1, Q2)");
            Check(vmax.MayReachSome("n6"), "n6 lies left of VMax in both lists");
            Check(!vmax.ReachesSome("n6"), "but n6 reaches neither n1 nor n7");
            CheckConstructed(t, r, ConstructedNodes.Of(t, set), set, "VMax counterexample");
        }

        public static void UMinCounterexample() {
            var (t, r) = Build(("r", "a"), ("r", "m"), ("r", "b"));
            var set = new List<string> { "a", "b" };
            var umin = t.UMin(set);
            Equal(umin.IndexNodes, ("a", "b"), "UMin index nodes (Q1, Q2)");
            Check(umin.MayBeReachedBySome("m"), "m = (2, 2) lies right of UMin = (1, 1) in both lists");
            Check(!umin.ReachedBySome("m"), "but neither a nor b reaches m");
            CheckConstructed(t, r, ConstructedNodes.Of(t, set), set, "UMin counterexample");
        }

        public static void UMinNestedMembers() {
            // s1 is an ancestor of v; s2 lies inside s1's subtree, left of v, and is the last
            // member before v in Q1. Only the topmost members may be searched.
            var (t, r) = Build(("r", "s1"), ("s1", "s2"), ("s1", "v"), ("r", "w"));
            var set = new List<string> { "s2", "s1" };
            var umin = t.UMin(set);
            Check(umin.ReachedBySome("v") && umin.ReachedBySome("s2"), "s1 reaches v and s2");
            Check(!umin.ReachedBySome("w") && !umin.ReachedBySome("s1"), "nothing in the set reaches w or s1");
            CheckConstructed(t, r, ConstructedNodes.Of(t, set), set, "nested members");
        }

        public static void ConstructedRandomSets() {
            for (int seed = 0; seed < 20; seed++) {
                var (t, r, rnd) = RandomTree(80, seed);
                var nodes = r.Nodes();
                foreach (int k in new[] { 1, 2, 5, 20 }) {
                    var set = nodes.OrderBy(_ => rnd.Next()).Take(k).ToList();
                    CheckConstructed(t, r, ConstructedNodes.Of(t, set), set, $"seed {seed}, k {k}");
                }
            }
        }

        public static void ConstructedIncrementalAdd() {
            var (t, r, rnd) = RandomTree(100, 3);
            var c = ConstructedNodes.Of(t, Array.Empty<string>());
            var set = new List<string>();
            foreach (var v in r.Nodes().OrderBy(_ => rnd.Next()).Take(15)) {
                c.VMin.Add(v);
                c.VMax.Add(v);
                c.UMin.Add(t.GetNode(v));
                c.UMax.Add(v);
                set.Add(v);
                CheckConstructed(t, r, c, set, $"after adding {v}");
            }
        }

        public static void ConstructedDiscard() {
            // random adds and discards, with inserts, deletes and moves in between
            for (int seed = 0; seed < 15; seed++) {
                var (t, r, rnd) = RandomTree(60, seed);
                var c = ConstructedNodes.Of(t, Array.Empty<string>());
                var set = new HashSet<string>();
                int k = 60;
                for (int step = 0; step < 120; step++) {
                    var nodes = r.Nodes();
                    var inner = nodes.Where(n => n != r.Root).ToList();
                    double x = rnd.NextDouble();
                    if (x < 0.35) {
                        var v = nodes[rnd.Next(nodes.Count)];
                        c.VMin.Add(v); c.VMax.Add(t.GetNode(v)); c.UMin.Add(v); c.UMax.Add(t.GetNode(v));
                        set.Add(v);
                    } else if (x < 0.65 && set.Count > 0) {
                        var v = set.OrderBy(n => n, StringComparer.Ordinal).ElementAt(rnd.Next(set.Count));
                        c.VMin.Discard(v); c.VMax.Discard(t.GetNode(v)); c.UMin.Discard(v); c.UMax.Discard(t.GetNode(v));
                        set.Remove(v);
                    } else if (x < 0.8) {
                        var p = nodes[rnd.Next(nodes.Count)];
                        t.Insert(p, $"x{k}");
                        r.Insert(p, $"x{k}");
                        k++;
                    } else if (x < 0.9 && inner.Count > 10) {
                        var v = inner[rnd.Next(inner.Count)];
                        t.Delete(v);
                        r.Delete(v);
                        set.Remove(v);
                    } else if (inner.Count > 10) {
                        var u = inner[rnd.Next(inner.Count)];
                        var banned = new HashSet<string>(t.Subtree(u));
                        var targets = nodes.Where(n => !banned.Contains(n)).ToList();
                        var p = targets[rnd.Next(targets.Count)];
                        t.CutNPaste(u, p);
                        r.Move(u, p);
                    }
                    var live = set.OrderBy(n => n, StringComparer.Ordinal).ToList();
                    CheckConstructed(t, r, c, live, $"seed {seed}, step {step}");
                    Seq(c.UMin.MemberNames.OrderBy(n => n, StringComparer.Ordinal), live, "members after discard");
                    foreach (var v in live.Take(3)) Check(c.VMax.Contains(v), $"Contains({v})");
                    foreach (var v in r.Nodes()) {                      // topmost member that reaches v
                        var above = r.Ancestors(v).Skip(1).Where(set.Contains).ToList();
                        Equal(c.UMin.Covering(v), above.Count > 0 ? above[^1] : null, $"seed {seed}, step {step}: Covering({v})");
                    }
                }
            }
            var t2 = new DTree();
            t2.Insert("a", "b");
            var u2 = t2.UMin(new[] { "b" });
            u2.Discard("a").Discard("nobody");
            Seq(u2.MemberNames, new[] { "b" }, "discarding a non-member is a no-op");
        }

        public static void NextInQ1() {
            var (t, _, _) = RandomTree(80, 7);
            var q1 = t.Q1.ToList();
            for (int i = 0; i < q1.Count; i++) {
                string? expected = i + 1 < q1.Count ? q1[i + 1] : null;
                Equal(t.NextInQ1(q1[i]), expected, $"NextInQ1({q1[i]})");
                Equal(t.NextInQ1(t.GetNode(q1[i]))?.Name, expected, $"NextInQ1(handle {q1[i]})");
            }
        }

        public static void ConstructedEmptySet() {
            var (t, _, _) = RandomTree(20, 1);
            var c = ConstructedNodes.Of(t, Array.Empty<string>());
            Check(c.VMin.ReachesAll("n3") && c.UMax.ReachedByAll("n3"), "all: vacuously true");
            Check(!c.VMax.MayReachSome("n3") && !c.VMax.ReachesSome("n3"), "reaches some: false");
            Check(!c.UMin.MayBeReachedBySome("n3") && !c.UMin.ReachedBySome("n3"), "reached by some: false");
            Check(!c.VMin.ReachesAll("missing"), "unknown node");
            Equal(c.VMin.IndexNodes, ((string?)null, (string?)null), "no index nodes");
        }

        public static void ConstructedSurvivesChanges() {
            for (int seed = 0; seed < 10; seed++) {
                var (t, r, rnd) = RandomTree(60, seed);
                var set = r.Nodes().Where(n => n != r.Root).OrderBy(_ => rnd.Next()).Take(5).ToList();
                var c = ConstructedNodes.Of(t, set);
                int next = 60;
                for (int step = 0; step < 40; step++) {
                    var nodes = r.Nodes();
                    var inner = nodes.Where(n => n != r.Root).ToList();
                    double x = rnd.NextDouble();
                    if (x < 0.5 || inner.Count < 5) {
                        var p = nodes[rnd.Next(nodes.Count)];
                        t.Insert(p, $"x{next}");
                        r.Insert(p, $"x{next}");
                        next++;
                    } else if (x < 0.65) {
                        var v = inner[rnd.Next(inner.Count)];
                        t.Delete(v);
                        r.Delete(v);
                    } else if (x < 0.75) {
                        var v = inner[rnd.Next(inner.Count)];
                        t.DeleteSubtree(v);
                        r.DeleteSubtree(v);
                    } else {
                        var u = inner[rnd.Next(inner.Count)];
                        var banned = new HashSet<string>(t.Subtree(u));
                        var targets = nodes.Where(n => !banned.Contains(n)).ToList();
                        var p = targets[rnd.Next(targets.Count)];
                        t.CutNPaste(u, p);
                        r.Move(u, p);
                    }
                    var live = set.Where(t.Contains).ToList();
                    CheckConstructed(t, r, c, live, $"seed {seed}, step {step}");
                    Seq(c.UMin.MemberNames.OrderBy(n => n, StringComparer.Ordinal), live.OrderBy(n => n, StringComparer.Ordinal), "members");
                }
            }
        }
    }

    internal static partial class Tests {
        private static string RefLast(Reference r, string v) {
            var w = v;
            while (r.Children.TryGetValue(w, out var kids) && kids.Count > 0) w = kids[^1];
            return w;
        }

        public static void SiblingInsertExample() {
            var t = new DTree();
            t.Insert("A", "B");
            t.Insert("A", "D");
            t.Insert("B", "C");
            t.InsertAfter("B", "X");                                    // A: B, X, D
            t.InsertBefore("B", "W");                                   // A: W, B, X, D
            t.InsertBefore("C", "C0");                                  // B: C0, C
            Seq(t.Children("A"), new[] { "W", "B", "X", "D" }, "children of A");
            Seq(t.Children("B"), new[] { "C0", "C" }, "children of B");
            Seq(t.Q1.ToList(), new[] { "A", "W", "B", "C0", "C", "X", "D" }, "Q1");
            Seq(t.Q2.ToList(), new[] { "A", "D", "X", "B", "C", "C0", "W" }, "Q2");
            Check(t.CanReach("A", "X") && !t.CanReach("B", "X"), "X is a child of A, not of B");
            Equal(t.SubtreeLast("A"), "D", "SubtreeLast(A)");
            Throws<InvalidOperationException>(() => t.InsertAfter("A", "Z"), "the root has no siblings");
            Throws<InvalidOperationException>(() => t.InsertBefore("A", "Z"), "the root has no siblings (before)");
            Throws<ArgumentException>(() => t.InsertAfter("B", "C"), "child already in the tree");
            Throws<KeyNotFoundException>(() => t.InsertAfter("nobody", "Z"), "sibling must exist");
            var n = t.InsertAfter(t.GetNode("D"), "E");
            Equal(n.Name, "E", "InsertAfter(handle) returns the new handle");
            Seq(t.Children("A"), new[] { "W", "B", "X", "D", "E" }, "children of A after E");
        }

        public static void SiblingInsertLines() {
            var t = new DTree();
            t.AddLine("A: B; D");
            t.AddLine("B > X; Y");                                      // X after B, Y after X
            t.AddLine("D < W1; W2");                                    // W1 before D, W2 before D
            t.AddLine("B: C");
            Seq(t.Children("A"), new[] { "B", "X", "Y", "W1", "W2", "D" }, "children of A");
            Seq(t.Children("B"), new[] { "C" }, "children of B");
        }

        public static void SiblingInsertRandomMix() {
            int saved = DTree.Budget;
            try {
                foreach (var budget in new[] { saved, 0 }) {
                    DTree.Budget = budget;
                    for (int seed = 0; seed < 15; seed++) {
                        var (t, r, rnd) = RandomTree(20, seed);
                        int k = 0;
                        for (int step = 0; step < 120; step++) {
                            var nodes = r.Nodes();
                            var inner = nodes.Where(n => n != r.Root).ToList();
                            double x = rnd.NextDouble();
                            var name = $"x{k}";
                            if (x < 0.25 || inner.Count == 0) {
                                var p = nodes[rnd.Next(nodes.Count)];
                                t.Insert(p, name);
                                r.Insert(p, name);
                                k++;
                            } else if (x < 0.5) {
                                var sb = inner[rnd.Next(inner.Count)];
                                t.InsertAfter(sb, name);
                                r.InsertAfter(sb, name);
                                k++;
                            } else if (x < 0.75) {
                                var sb = inner[rnd.Next(inner.Count)];
                                t.InsertBefore(sb, name);
                                r.InsertBefore(sb, name);
                                k++;
                            } else if (x < 0.85 && inner.Count > 10) {
                                var v = inner[rnd.Next(inner.Count)];
                                t.Delete(v);
                                r.Delete(v);
                            } else if (inner.Count > 10) {
                                var u = inner[rnd.Next(inner.Count)];
                                var banned = new HashSet<string>(t.Subtree(u));
                                var targets = nodes.Where(n => !banned.Contains(n)).ToList();
                                var p = targets[rnd.Next(targets.Count)];
                                t.CutNPaste(u, p);
                                r.Move(u, p);
                            }
                            CheckAgainst(t, r, rnd);
                            foreach (var v in r.Nodes().OrderBy(_ => rnd.Next()).Take(3))
                                Equal(t.SubtreeLast(v), RefLast(r, v), $"seed {seed}, step {step}: SubtreeLast({v})");
                        }
                    }
                }
            } finally {
                DTree.Budget = saved;
            }
        }

        public static void SiblingInsertSameGap() {
            // repeated insertion into the same gap from both sides: positions stay strictly increasing
            var t = new DTree();
            var r = new Reference();
            t.Insert("r", "a"); r.Insert("r", "a");
            t.Insert("r", "b"); r.Insert("r", "b");
            string left = "a", right = "b";
            for (int i = 0; i < 400; i++) {
                if (i % 2 == 1) {
                    t.InsertAfter(left, $"l{i}"); r.InsertAfter(left, $"l{i}"); left = $"l{i}";
                } else {
                    t.InsertBefore(right, $"r{i}"); r.InsertBefore(right, $"r{i}"); right = $"r{i}";
                }
            }
            CheckAgainst(t, r, new Random(1));
        }

        public static void SubtreeEndTopDownComb() {
            // a chain, then new leaves under the spine nodes from the top down: the plain walk
            // would be O(depth) per insertion here
            var t = new DTree();
            var r = new Reference();
            const int d = 300;
            for (int i = 1; i < d; i++) {
                t.Insert($"n{i - 1}", $"n{i}");
                r.Insert($"n{i - 1}", $"n{i}");
            }
            int k = d;
            for (int round = 0; round < 3; round++)
                for (int i = 0; i < d; i++) {
                    t.Insert($"n{i}", $"x{k}");
                    r.Insert($"n{i}", $"x{k}");
                    k++;
                }
            CheckAgainst(t, r, new Random(1));
            foreach (var v in r.Nodes().OrderBy(_ => Guid.NewGuid()).Take(50))
                Equal(t.SubtreeLast(v), RefLast(r, v), $"SubtreeLast({v})");
        }

        public static void SubtreeEndMixed() {
            for (int seed = 0; seed < 25; seed++) {
                var (t, r, rnd) = RandomTree(40, seed);
                int k = 40;
                for (int step = 0; step < 150; step++) {
                    var nodes = r.Nodes();
                    var inner = nodes.Where(n => n != r.Root).ToList();
                    double x = rnd.NextDouble();
                    if (x < 0.55 || inner.Count < 8) {
                        var p = rnd.NextDouble() < 0.5 ? nodes[rnd.Next(nodes.Count)] : RefLast(r, nodes[rnd.Next(nodes.Count)]);
                        if (rnd.NextDouble() < 0.3) p = r.Root!;
                        t.Insert(p, $"x{k}");
                        r.Insert(p, $"x{k}");
                        k++;
                    } else if (x < 0.7) {
                        var v = inner[rnd.Next(inner.Count)];
                        t.Delete(v);
                        r.Delete(v);
                    } else if (x < 0.8) {
                        var v = inner[rnd.Next(inner.Count)];
                        t.DeleteSubtree(v);
                        r.DeleteSubtree(v);
                    } else {
                        var u = inner[rnd.Next(inner.Count)];
                        var banned = new HashSet<string>(t.Subtree(u));
                        var targets = nodes.Where(n => !banned.Contains(n)).ToList();
                        var p = targets[rnd.Next(targets.Count)];
                        t.CutNPaste(u, p);
                        r.Move(u, p);
                    }
                    if (step % 10 == 0)
                        foreach (var v in r.Nodes().OrderBy(_ => rnd.Next()).Take(10))
                            Equal(t.SubtreeLast(v), RefLast(r, v), $"seed {seed}, step {step}: SubtreeLast({v})");
                }
                CheckAgainst(t, r, rnd);
            }
        }

        public static void SubtreeEndHintPathAlways() {
            int saved = DTree.Budget;
            DTree.Budget = 0;           // every lookup of a subtree's end goes through the validated hint
            try {
                SubtreeEndMixed();
                SubtreeEndTopDownComb();
            } finally {
                DTree.Budget = saved;
            }
        }
    }

    /// <summary>Runs the benchmarks and writes their output as a dated Markdown report.</summary>
    internal static class Report {
        private sealed class Tee : TextWriter {
            public readonly TextWriter Console;
            public readonly StringBuilder Copy = new();
            public Tee(TextWriter console) { Console = console; }
            public override Encoding Encoding => Console.Encoding;
            public override void Write(char value) { Console.Write(value); Copy.Append(value); }
            public override void Write(string? value) { Console.Write(value); Copy.Append(value); }
            public override void Write(char[] buffer, int index, int count) { Console.Write(buffer, index, count); Copy.Append(buffer, index, count); }
            public override void Flush() => Console.Flush();
        }

        public static void RunBench(string[] args) {
            // Same number format as the Python report (10,000 and 0.013), whatever the system's culture.
            CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
            bool save = true, dynamic = false;
            string note = "";
            var sizes = new List<int>();
            for (int i = 0; i < args.Length; i++) {
                if (args[i] == "--no-save") save = false;
                else if (args[i] == "--note" && i + 1 < args.Length) note = args[++i];
                else if (args[i] == "dynamic") dynamic = true;
                else sizes.Add(int.Parse(args[i], CultureInfo.InvariantCulture));
            }
            var started = DateTime.Now;
            var console = System.Console.Out;
            var tee = save ? new Tee(console) : null;
            if (tee != null) System.Console.SetOut(tee);
            try {
                if (dynamic) Bench.RunDynamic();
                else Bench.Run(sizes.ToArray());
            } finally {
                if (tee != null) {
                    System.Console.SetOut(console);
                    var shown = string.Join(" ", args.Select(a => a.Contains(' ') ? $"\"{a}\"" : a));
                    var path = Write(tee.Copy.ToString(), started, shown, note);
                    System.Console.WriteLine($"\nReport written to {path}");
                }
            }
        }

        private static string RepoRoot() {
            for (var d = new DirectoryInfo(AppContext.BaseDirectory); d != null; d = d.Parent)
                if (Directory.Exists(Path.Combine(d.FullName, "csharp")) && Directory.Exists(Path.Combine(d.FullName, "python")))
                    return d.FullName;
            return Directory.GetCurrentDirectory();
        }

        private static string Processor() {
            var id = Environment.GetEnvironmentVariable("PROCESSOR_IDENTIFIER");     // Windows
            if (!string.IsNullOrEmpty(id)) return id;
            try {
                foreach (var line in File.ReadLines("/proc/cpuinfo"))
                    if (line.StartsWith("model name")) return line.Split(':', 2)[1].Trim();
            } catch (IOException) { } catch (UnauthorizedAccessException) { }
            return RuntimeInformation.ProcessArchitecture.ToString();
        }

        private static string Write(string body, DateTime started, string shownArgs, string note) {
            var root = RepoRoot();
            var dir = Path.Combine(root, "benchmarks", "csharp");
            Directory.CreateDirectory(dir);
            var path = Path.Combine(dir, started.ToString("yyyy-MM-dd_HH-mm", CultureInfo.InvariantCulture) + ".md");
            var v = typeof(DTree).Assembly.GetName().Version;
            var head = new List<string> {
                $"# DTree benchmarks, C#—{started.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture)}",
                "",
                $"- DTree {v?.ToString(3)}, {RuntimeInformation.FrameworkDescription}",
                $"- {RuntimeInformation.OSDescription} ({RuntimeInformation.OSArchitecture})",
                $"- Processor: {Processor()}, {Environment.ProcessorCount} logical cores",
                $"- Command: `dotnet run --project csharp/Triordinal.DTree.Tests -c Release -- bench{(shownArgs.Length > 0 ? " " + shownArgs : "")}`",
            };
            if (note.Length > 0) head.Add($"- Note: {note}");
            var lines = body.Replace("\r\n", "\n").Split('\n').ToList();
            if (lines.Count > 0 && lines[0].StartsWith("DTree ")) lines.RemoveAt(0);   // replaced by the header
            while (lines.Count > 0 && lines[0].Length == 0) lines.RemoveAt(0);
            File.WriteAllText(path, string.Join("\n", head) + "\n\n" + string.Join("\n", lines).TrimEnd() + "\n", new UTF8Encoding(false));
            return Path.GetRelativePath(root, path);
        }
    }

    internal static class Bench {
        private static readonly (string Name, Func<int, List<string>, Random, string> Parent)[] Shapes = {
            ("random", (i, names, rnd) => names[rnd.Next(names.Count)]),
            ("chain", (i, names, rnd) => names[^1]),
            ("star (root)", (i, names, rnd) => "n0"),
            ("star (inner node)", (i, names, rnd) => i <= 2 ? "n0" : "n1"),
            ("alternating", (i, names, rnd) => $"n{2 * ((i - 1) / 2)}"),
            // a chain of 3,000, then new leaves under the spine nodes from the top down, repeatedly:
            // finding the end of a subtree by walking down the last children would be O(depth) here
            ("top-down comb", (i, names, rnd) => i < 3000 ? names[^1] : $"n{(i - 3000) % 3000}"),
        };

        private static (DTree Tree, List<string> Names, double Seconds) Build(int shape, int n, int seed = 1) {
            var rnd = new Random(seed);
            var t = new DTree("B");
            var names = new List<string> { "n0" };
            var sw = Stopwatch.StartNew();
            for (int i = 1; i < n; i++) {
                t.Insert(Shapes[shape].Parent(i, names, rnd), $"n{i}");
                names.Add($"n{i}");
            }
            return (t, names, sw.Elapsed.TotalSeconds);
        }

        public static void Run(int[] sizes) {
            if (sizes.Length == 0) sizes = new[] { 10_000, 100_000 };
            Console.WriteLine($"DTree benchmarks (C#, .NET {Environment.Version})\n");
            Console.WriteLine("| shape | nodes | time [s] | renumberings Q1 / Q2 | positions moved per insertion |");
            Console.WriteLine("| --- | ---: | ---: | ---: | ---: |");
            for (int s = 0; s < Shapes.Length; s++)
                foreach (var n in sizes) {
                    var (t, _, sec) = Build(s, n);
                    double moved = (t.Q1.RenumberMoved + t.Q2.RenumberMoved) / (2.0 * n);
                    Console.WriteLine($"| {Shapes[s].Name} | {n:N0} | {sec:F3} | {t.Q1.RenumberCount:N0} / {t.Q2.RenumberCount:N0} | {moved:F2} |");
                }

            int big = sizes.Max();
            var (tree, nodes, _) = Build(0, big);
            var rnd = new Random(2);
            const int queries = 1_000_000;
            var pairs = new (string, string)[queries];
            for (int i = 0; i < queries; i++) pairs[i] = (nodes[rnd.Next(nodes.Count)], nodes[rnd.Next(nodes.Count)]);
            var sw = Stopwatch.StartNew();
            int hits = 0;
            foreach (var (u, v) in pairs) if (tree.CanReach(u, v)) hits++;
            double perQuery = sw.Elapsed.TotalMilliseconds * 1000 / queries;
            Console.WriteLine($"\nCanReach on a random tree of {big:N0} nodes: {perQuery:F3} µs per call with names ({hits:N0} of {queries:N0} reachable)");
            var handles = new (DNode, DNode)[queries];
            for (int i = 0; i < queries; i++) handles[i] = (tree.GetNode(pairs[i].Item1), tree.GetNode(pairs[i].Item2));
            sw.Restart();
            int hits2 = 0;
            foreach (var (u, v) in handles) if (tree.CanReach(u, v)) hits2++;
            double perHandle = sw.Elapsed.TotalMilliseconds * 1000 / queries;
            Console.WriteLine($"CanReach on a random tree of {big:N0} nodes: {perHandle:F3} µs per call with node handles ({hits2:N0} reachable)");

            Depth(100_000, new[] { 10, 100, 1_000, 10_000, 100_000 }, 50_000);
            Sets(100_000, new[] { 10, 100, 1_000, 10_000 }, 1_000, 200);
            Dynamic(100_000, new[] { 10, 100, 1_000, 10_000, 100_000 }, new[] { 1_000, 10_000, 20_000 });
            TreeView(100_000, new[] { 10, 100, 1_000, 10_000, 100_000 }, 20_000);
        }

        public static void RunDynamic() {
            Console.WriteLine($"DTree dynamic updates (C#, .NET {Environment.Version})");
            Dynamic(100_000, new[] { 10, 100, 1_000, 10_000, 100_000 }, new[] { 1_000, 10_000, 20_000 });
            TreeView(100_000, new[] { 10, 100, 1_000, 10_000, 100_000 }, 20_000);
        }

        // -- dynamic updates: insertions and queries alternating --------------------------------

        /// <summary>A classical tree node: parent link and child list.</summary>
        private sealed class PNode {
            public PNode? Parent;
            public readonly List<PNode> Kids = new();
            public readonly int Id;
            public PNode(int id) { Id = id; }
        }

        private sealed record Step(int Parent, int Child, (int U, int V)[] Queries);

        /// <summary>The same sequence for every contender: insertions (a spine of depth nodes, the others
        /// attached at random to spine nodes) with random queries among the nodes present.</summary>
        private static Step[] Workload(int n, int depth, int queriesPerInsert, int seed = 5) {
            var rnd = new Random(seed);
            var steps = new Step[n - 1];
            for (int i = 1; i < n; i++) {
                int parent = i < depth ? i - 1 : rnd.Next(Math.Min(depth, i));
                var qs = new (int, int)[queriesPerInsert];
                for (int q = 0; q < queriesPerInsert; q++) qs[q] = (rnd.Next(i + 1), rnd.Next(i + 1));
                steps[i - 1] = new Step(parent, i, qs);
            }
            return steps;
        }

        private static (double Ms, List<bool> Answers) RunDTree(Step[] steps) {
            var answers = new List<bool>(steps.Length);
            var sw = Stopwatch.StartNew();
            var t = new DTree("D");
            var nodes = new DNode[steps.Length + 1];
            foreach (var s in steps) {
                if (s.Child == 1) {
                    nodes[1] = t.Insert("n0", "n1");
                    nodes[0] = t.GetNode("n0");
                } else {
                    nodes[s.Child] = t.Insert(nodes[s.Parent], $"n{s.Child}");
                }
                foreach (var (u, v) in s.Queries) answers.Add(t.CanReach(nodes[u], nodes[v]));
            }
            return (sw.Elapsed.TotalMilliseconds, answers);
        }

        private static (double Ms, List<bool> Answers) RunParentWalk(Step[] steps) {
            var answers = new List<bool>(steps.Length);
            var sw = Stopwatch.StartNew();
            var nodes = new PNode[steps.Length + 1];
            nodes[0] = new PNode(0);
            foreach (var s in steps) {
                var c = new PNode(s.Child) { Parent = nodes[s.Parent] };
                nodes[s.Parent].Kids.Add(c);
                nodes[s.Child] = c;
                foreach (var (u, v) in s.Queries) {
                    bool hit = false;
                    for (var w = nodes[v].Parent; w != null; w = w.Parent)
                        if (w == nodes[u]) { hit = true; break; }
                    answers.Add(hit);
                }
            }
            return (sw.Elapsed.TotalMilliseconds, answers);
        }

        /// <summary>Pre- and post-order numbers from a traversal, recomputed before a query whenever the
        /// tree has changed: O(1) queries, but every insertion invalidates all numbers.</summary>
        private static (double Ms, List<bool> Answers) RunStaticNumbers(Step[] steps) {
            var answers = new List<bool>(steps.Length);
            var sw = Stopwatch.StartNew();
            int n = steps.Length + 1;
            var nodes = new PNode[n];
            nodes[0] = new PNode(0);
            var pre = new int[n];
            var post = new int[n];
            var stack = new Stack<(PNode Node, bool Done)>();
            foreach (var s in steps) {
                var c = new PNode(s.Child) { Parent = nodes[s.Parent] };
                nodes[s.Parent].Kids.Add(c);
                nodes[s.Child] = c;
                bool valid = false;                                     // the insertion invalidates the numbers
                foreach (var (u, v) in s.Queries) {
                    if (!valid) {
                        int clock = 0;
                        stack.Push((nodes[0], false));
                        while (stack.Count > 0) {
                            var (x, done) = stack.Pop();
                            if (done) { post[x.Id] = clock++; continue; }
                            pre[x.Id] = clock++;
                            stack.Push((x, true));
                            for (int k = x.Kids.Count - 1; k >= 0; k--) stack.Push((x.Kids[k], false));
                        }
                        valid = true;
                    }
                    answers.Add(pre[u] < pre[v] && post[v] < post[u]);
                }
            }
            return (sw.Elapsed.TotalMilliseconds, answers);
        }

        private static string Factor(double slow, double fast) =>
            (slow < 10 * fast ? (slow / fast).ToString("F1") : (slow / fast).ToString("N0")) + "×";

        /// <summary>Best of three runs, or a single run if it takes over two seconds (noise is small then).</summary>
        private static (double Ms, List<bool> Answers) Best(Func<Step[], (double Ms, List<bool> Answers)> run, Step[] steps) {
            var (ms, answers) = run(steps);
            if (ms < 2000)
                for (int i = 0; i < 2; i++) ms = Math.Min(ms, run(steps).Ms);
            return (ms, answers);
        }

        private static void Dynamic(int n, int[] depths, int[] staticSizes) {
            RunDTree(Workload(1_000, 10, 10));                          // warm-up (JIT)
            RunParentWalk(Workload(1_000, 10, 10));
            RunStaticNumbers(Workload(200, 10, 1));
            Console.WriteLine($"\nDynamic updates: insertions and queries alternating ({n:N0} nodes, node handles)\n");
            Console.WriteLine("A step is one insertion followed by 1 or 10 queries between random nodes present at that moment; µs per step, best of three runs.\n");
            Console.WriteLine("| depth | DTree, 1 query | parent walk, 1 query | factor | DTree, 10 queries | parent walk, 10 queries | factor |");
            Console.WriteLine("| ---: | ---: | ---: | ---: | ---: | ---: | ---: |");
            foreach (var depth in depths) {
                var line = $"| {depth:N0} |";
                foreach (var q in new[] { 1, 10 }) {
                    var steps = Workload(n, depth, q);
                    var (d, a) = Best(RunDTree, steps);
                    var (w, b) = Best(RunParentWalk, steps);
                    if (!a.SequenceEqual(b)) throw new InvalidOperationException("DTree and parent walk disagree");
                    line += $" {d * 1000 / steps.Length:F3} | {w * 1000 / steps.Length:F3} | {Factor(w, d)} |";
                }
                Console.WriteLine(line);
            }
            Console.WriteLine("\nDynamic updates with static pre/post numbers, recomputed after each insertion (1 query per insertion)\n");
            Console.WriteLine("The tree keeps the given depth as it grows: more nodes make it wider, not deeper. Total time in ms.\n");
            Console.WriteLine("| depth | nodes | DTree [ms] | parent walk [ms] | static numbers [ms] |");
            Console.WriteLine("| ---: | ---: | ---: | ---: | ---: |");
            foreach (var depth in new[] { 100, 1_000 })
                foreach (var m in staticSizes) {
                    var steps = Workload(m, depth, 1);
                    var (d, a) = Best(RunDTree, steps);
                    var (w, b) = Best(RunParentWalk, steps);
                    var (r, c) = RunStaticNumbers(steps);
                    if (!a.SequenceEqual(b) || !a.SequenceEqual(c)) throw new InvalidOperationException("answers disagree");
                    Console.WriteLine($"| {depth:N0} | {m:N0} | {d:F1} | {w:F1} | {r:N0} |");
                }
        }

        // -- use case: a tree view with expand/collapse -----------------------------------------

        /// <summary>Classical tree model for a tree view: parent link, child list, next-sibling link, collapsed flag.</summary>
        private sealed class TNode {
            public readonly int Id;
            public TNode? Parent;
            public TNode? NextSib;
            public readonly List<TNode> Kids = new();
            public bool Collapsed;
            public TNode(int id) { Id = id; }
        }

        /// <summary>Insert leaf B under spine node A, or toggle spine node A (B = -1); then show node V.</summary>
        private readonly record struct ViewOp(bool Insert, int A, int B, int V);

        /// <summary>Changes to a tree built by BuildWithDepth(n, depth): each step inserts a leaf under a random
        /// spine node or toggles (collapses or expands) a random spine node, then names a random node to show.</summary>
        private static ViewOp[] TreeViewWorkload(int n, int depth, int steps, int seed = 6) {
            var rnd = new Random(seed);
            var ops = new ViewOp[steps];
            int size = n;
            for (int i = 0; i < steps; i++) {
                bool insert = rnd.NextDouble() < 0.5;
                int a = rnd.Next(depth);
                int b = insert ? size++ : -1;
                ops[i] = new ViewOp(insert, a, b, rnd.Next(size));
            }
            return ops;
        }

        /// <summary>DTree: the collapsed nodes are one UMin. The visible row that contains v is Covering(v)
        /// (v itself if null); the rows below follow Q1, jumping over every collapsed subtree with SubtreeLast.</summary>
        private static (double Ms, List<int[]> Rows) TreeViewDTree(DTree t, List<DNode> nodes, ViewOp[] ops, int rows) {
            var collapsed = t.UMin(Array.Empty<DNode>());
            var shown = new List<DNode[]>(ops.Length);
            var buf = new List<DNode>(rows);
            var sw = Stopwatch.StartNew();
            foreach (var op in ops) {
                if (op.Insert) nodes.Add(t.Insert(nodes[op.A], $"n{op.B}"));
                else if (collapsed.Contains(nodes[op.A])) collapsed.Discard(nodes[op.A]);
                else collapsed.Add(nodes[op.A]);
                var x = collapsed.Covering(nodes[op.V]) ?? nodes[op.V];
                buf.Clear();
                buf.Add(x);
                while (buf.Count < rows) {
                    if (collapsed.Contains(x)) x = t.SubtreeLast(x);
                    var next = t.NextInQ1(x);
                    if (next == null) break;
                    x = next;
                    buf.Add(x);
                }
                shown.Add(buf.ToArray());
            }
            double ms = sw.Elapsed.TotalMilliseconds;
            return (ms, shown.Select(r => r.Select(d => int.Parse(d.Name.AsSpan(1), NumberStyles.Integer, CultureInfo.InvariantCulture)).ToArray()).ToList());
        }

        /// <summary>Classical: the visible row that contains v is its topmost collapsed ancestor (one climb to the
        /// root); the next row is the first child of an expanded node, otherwise the next sibling of the node or
        /// of its nearest ancestor that has one.</summary>
        private static (double Ms, List<int[]> Rows) TreeViewWalk(List<TNode> nodes, ViewOp[] ops, int rows) {
            var shown = new List<int[]>(ops.Length);
            var buf = new List<int>(rows);
            var sw = Stopwatch.StartNew();
            foreach (var op in ops) {
                if (op.Insert) {
                    var p = nodes[op.A];
                    var c = new TNode(op.B) { Parent = p };
                    if (p.Kids.Count > 0) p.Kids[^1].NextSib = c;
                    p.Kids.Add(c);
                    nodes.Add(c);
                } else {
                    nodes[op.A].Collapsed = !nodes[op.A].Collapsed;
                }
                var v = nodes[op.V];
                TNode? top = null;
                for (var w = v.Parent; w != null; w = w.Parent)
                    if (w.Collapsed) top = w;
                var x = top ?? v;
                buf.Clear();
                buf.Add(x.Id);
                while (buf.Count < rows) {
                    if (x.Kids.Count > 0 && !x.Collapsed) {
                        x = x.Kids[0];
                    } else {
                        TNode? y = x;
                        while (y != null && y.NextSib == null) y = y.Parent;
                        if (y == null) break;
                        x = y.NextSib!;
                    }
                    buf.Add(x.Id);
                }
                shown.Add(buf.ToArray());
            }
            return (sw.Elapsed.TotalMilliseconds, shown);
        }

        private static List<TNode> ClassicalCopy(List<DNode> nodes) {
            var index = new Dictionary<DNode, int>();
            for (int i = 0; i < nodes.Count; i++) index[nodes[i]] = i;
            var copy = new List<TNode>(nodes.Count);
            for (int i = 0; i < nodes.Count; i++) copy.Add(new TNode(i));
            for (int i = 1; i < nodes.Count; i++) {                     // ids increase in insertion order
                var p = copy[index[nodes[i].Parent!]];
                var c = copy[i];
                c.Parent = p;
                if (p.Kids.Count > 0) p.Kids[^1].NextSib = c;
                p.Kids.Add(c);
            }
            return copy;
        }

        private static void TreeView(int n, int[] depths, int steps, int rows = 20) {
            {                                                           // warm-up (JIT)
                var (t0, nodes0) = BuildWithDepth(2_000, 10);
                var copy0 = ClassicalCopy(nodes0);
                var ops0 = TreeViewWorkload(2_000, 10, 500);
                TreeViewDTree(t0, nodes0, ops0, rows);
                TreeViewWalk(copy0, ops0, rows);
            }
            Console.WriteLine($"\nUse case: tree view with expand/collapse ({n:N0} nodes, {steps:N0} steps, node handles)\n");
            Console.WriteLine($"Each step changes the tree (inserts a leaf or collapses/expands a node, half and half), then shows a random node: it finds the visible row that contains it and lists the {rows} visible rows from there. µs per step, best of three runs.\n");
            Console.WriteLine("| depth | DTree [µs per step] | parent walk [µs per step] | factor |");
            Console.WriteLine("| ---: | ---: | ---: | ---: |");
            foreach (var depth in depths) {
                var ops = TreeViewWorkload(n, depth, steps);
                double d = double.MaxValue, w = double.MaxValue;
                int reps = 3;
                for (int rep = 0; rep < reps; rep++) {
                    var (t, nodes) = BuildWithDepth(n, depth);
                    var copy = ClassicalCopy(nodes);
                    var (dm, a) = TreeViewDTree(t, nodes, ops, rows);
                    var (wm, b) = TreeViewWalk(copy, ops, rows);
                    if (a.Count != b.Count || !a.Zip(b).All(p => p.First.SequenceEqual(p.Second)))
                        throw new InvalidOperationException("tree view: DTree and parent walk disagree");
                    d = Math.Min(d, dm);
                    w = Math.Min(w, wm);
                    if (dm > 2000 && wm > 2000) reps = 1;               // long runs: noise is small
                }
                Console.WriteLine($"| {depth:N0} | {d * 1000 / steps:F2} | {w * 1000 / steps:F2} | {Factor(w, d)} |");
            }
        }

        /// <summary>A spine (chain) of depth nodes; all other nodes hang at random under spine nodes.</summary>
        private static (DTree Tree, List<DNode> Nodes) BuildWithDepth(int n, int depth, int seed = 1) {
            var rnd = new Random(seed);
            var t = new DTree("D");
            var nodes = new List<DNode>();
            for (int i = 1; i < n; i++) {
                if (i == 1) {
                    t.Insert("n0", "n1");
                    nodes.Add(t.GetNode("n0"));
                    nodes.Add(t.GetNode("n1"));
                    continue;
                }
                var parent = i < depth ? nodes[^1] : nodes[rnd.Next(Math.Min(depth, nodes.Count))];
                nodes.Add(t.Insert(parent, $"n{i}"));
            }
            return (t, nodes);
        }

        /// <summary>What classical doubly linked trees do: climb from v towards the root, looking for u.</summary>
        private static bool ParentWalk(DNode u, DNode v) {
            for (var w = v.Parent; w != null; w = w.Parent)
                if (w == u) return true;
            return false;
        }

        /// <summary>Climb once from v towards the root and count the ancestors of v that lie in members.</summary>
        private static int AncestorsIn(DNode v, HashSet<DNode> members) {
            int hits = 0;
            for (var w = v.Parent; w != null; w = w.Parent)
                if (members.Contains(w)) hits++;
            return hits;
        }

        private static void Depth(int n, int[] depths, int queries) {
            Console.WriteLine($"\nReachability by depth: DTree vs parent walk ({n:N0} nodes, {queries:N0} random pairs, node handles)\n");
            Console.WriteLine("| depth | DTree [µs] | parent walk [µs] | factor |");
            Console.WriteLine("| ---: | ---: | ---: | ---: |");
            foreach (var depth in depths) {
                var (t, nodes) = BuildWithDepth(n, depth);
                var rnd = new Random(2);
                var pairs = new (DNode, DNode)[queries];
                for (int i = 0; i < queries; i++) pairs[i] = (nodes[rnd.Next(nodes.Count)], nodes[rnd.Next(nodes.Count)]);
                var a = new bool[queries];
                var b = new bool[queries];
                for (int i = 0; i < 100; i++) { t.CanReach(pairs[i].Item1, pairs[i].Item2); ParentWalk(pairs[i].Item1, pairs[i].Item2); }   // warm-up (JIT)
                var sw = Stopwatch.StartNew();
                for (int i = 0; i < queries; i++) a[i] = t.CanReach(pairs[i].Item1, pairs[i].Item2);
                double d = sw.Elapsed.TotalMilliseconds * 1000 / queries;
                sw.Restart();
                for (int i = 0; i < queries; i++) b[i] = ParentWalk(pairs[i].Item1, pairs[i].Item2);
                double w = sw.Elapsed.TotalMilliseconds * 1000 / queries;
                if (!a.SequenceEqual(b)) throw new InvalidOperationException("DTree and parent walk disagree");
                Console.WriteLine($"| {depth:N0} | {d:F3} | {w:F3} | {w / d:N1}× |");
            }
        }

        private static void Sets(int n, int[] depths, int k, int queries) {
            Console.WriteLine($"\nAnd/or queries: constructed nodes vs parent walk ({n:N0} nodes, set of {k:N0} nodes; DTree 100,000 and parent walk {queries:N0} random query nodes)\n");
            Console.WriteLine("| depth | question | DTree [µs] | parent walk [µs] | factor |");
            Console.WriteLine("| ---: | --- | ---: | ---: | ---: |");
            double build = 0;
            foreach (var depth in depths) {
                var (t, nodes) = BuildWithDepth(n, depth);
                var rnd = new Random(4);
                var set = nodes.OrderBy(_ => rnd.Next()).Take(k).ToList();
                var us = Enumerable.Range(0, queries).Select(_ => nodes[rnd.Next(nodes.Count)]).ToArray();
                // DTree is fast, so it answers many different random query nodes (no cache or
                // branch-predictor advantage from repeating the same ones); the parent walk answers
                // the first `queries` of them, and both are compared on those.
                var many = us.Concat(Enumerable.Range(0, 100_000 - queries).Select(_ => nodes[rnd.Next(nodes.Count)])).ToArray();
                var sw = Stopwatch.StartNew();
                var vmin = t.VMin(set);
                var vmax = t.VMax(set);
                var umin = t.UMin(set);
                var umax = t.UMax(set);
                build = sw.Elapsed.TotalMilliseconds;
                var members = new HashSet<DNode>(set);
                // "reaches": climb from every member looking for u. "reached by": climb once from u,
                // looking each ancestor up in a hash set of the members (the best a parent walk can do).
                var questions = new (string Name, Func<DNode, bool> V, Func<DNode, bool> Walk)[] {
                    ("reaches all", u => vmin.ReachesAll(u), u => set.All(v => ParentWalk(u, v))),
                    ("reaches some", u => vmax.ReachesSome(u), u => set.Any(v => ParentWalk(u, v))),
                    ("reached by all", u => umax.ReachedByAll(u), u => AncestorsIn(u, members) == members.Count),
                    ("reached by some", u => umin.ReachedBySome(u), u => AncestorsIn(u, members) > 0),
                };
                foreach (var (name, v, walk) in questions) {
                    foreach (var u in us.Take(20)) { v(u); walk(u); }    // warm-up (JIT)
                    int sink = 0;
                    sw.Restart();
                    foreach (var u in many) if (v(u)) sink++;
                    double d = sw.Elapsed.TotalMilliseconds * 1000 / many.Length;
                    var a = us.Select(v).ToArray();
                    if (sink < 0) Console.Write("");
                    sw.Restart();
                    var b = us.Select(walk).ToArray();
                    double w = sw.Elapsed.TotalMilliseconds * 1000 / queries;
                    if (!a.SequenceEqual(b)) throw new InvalidOperationException($"{name}: DTree and parent walk disagree");
                    Console.WriteLine($"| {depth:N0} | {name} | {d:F3} | {w:F1} | {Factor(w, d)} |");
                }
            }
            Console.WriteLine($"\n(Building VMin, VMax, UMin and UMax for {k:N0} nodes: {build:F2} ms, once per set.)");
        }
    }
}
