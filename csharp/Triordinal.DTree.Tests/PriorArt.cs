// Prior art for the benchmarks, ported from python/dtree/triordinal/dtree/prior_art.py (the reference):
// classical encodings of ancestry, implemented as fairly as DTree itself, so that the benchmarks
// compare methods rather than implementations.
//
// * EulerTour: the parenthesis (Euler-tour) encoding on one list. Every node has an open and a close
//   cell in one DList; u is an ancestor of v exactly when v's open cell lies between u's open and close
//   cells (Dietz 1982; order maintenance: Dietz & Sleator 1987, Bender et al. 2002). The list is the
//   same DList with rational positions that DTree uses, so the only difference is one list instead of two.
//   It keeps no parent or child links (DTree does), so its insertions do less bookkeeping.
// * PrePostNumbers: pre- and post-order numbers from a traversal, recomputed lazily: only before a
//   query, and only if the tree has changed since the last traversal.
// * IntList and EulerTourInt: the same Euler tour on a list with integer labels, as in classical order
//   maintenance: midpoints in [0, 2^62]; when no integer is left between two neighbors, the smallest
//   surrounding region with enough room is relabeled evenly, with the same density rule as DList.
//   Compared with EulerTour, this isolates rational against integer positions.
// * NumList<T> and EulerTourNum<T>: the same Euler tour on floating-point positions, double or decimal.
//   A new cell gets one unit beyond its neighbor next to SOURCE or SINK, as rational positions do;
//   between two cells, a double gets the midpoint, and a decimal the left neighbor plus half the gap
//   rounded at its most significant digit, as in the original List.cs of DTree 1.0.0 (Enis Olgac's
//   prototype). When no representable position is left between the neighbors, a region is respaced
//   evenly, with the same density rule.
//
// Both answer and/or queries with the same kind of constructed points as DTree (minimum and maximum of
// the open and close positions, or of the numbers, over the set).

using System.Numerics;
using System.Runtime.CompilerServices;
using Triordinal;

namespace DirectedTrees.Tests {

    internal sealed class ENode {
        public readonly string Name;
        internal readonly EulerTour Owner;
        internal DList.Cell O = null!;          // open cell
        internal DList.Cell C = null!;          // close cell
        public ENode(string name, EulerTour owner) { Name = name; Owner = owner; }
    }

    internal sealed class EulerTour {
        private readonly DList _q;
        private readonly Dictionary<string, ENode> _nodes = new();
        public ENode? Root;

        public EulerTour(string name = "E") { _q = new DList(name); }

        public DList List => _q;
        public int Count => _nodes.Count;
        public ENode GetNode(string name) => _nodes[name];

        private ENode New(string name, DList.Cell after) {
            var n = new ENode(name, this);
            n.O = _q.InsertNewAfter(name, after);
            n.C = _q.InsertNewAfter(null, n.O);
            n.O.Node = n.C.Node = n;
            _nodes[name] = n;
            return n;
        }

        public ENode Insert(string parent, string child) {
            if (Root == null) Root = New(parent, _q.FirstCell);
            return Insert(_nodes[parent], child);
        }

        public ENode Insert(ENode parent, string child) {
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            return New(child, parent.C.Prev!);                       // last child: before the parent's close cell
        }

        /// <summary>Same argument handling as DTree.CanReach on handles: foreign handles reach nothing.</summary>
        public bool CanReach(ENode u, ENode v) =>
            u.Owner == this && v.Owner == this && DList.Less(u.O, v.O) && DList.Less(v.O, u.C);

        public bool CanReach(string u, string v) =>
            _nodes.TryGetValue(u, out var a) && _nodes.TryGetValue(v, out var b) && CanReach(a, b);

        public EulerSet Set(IEnumerable<ENode> nodes) => new(nodes);
    }

    /// <summary>The constructed points of a node set in an Euler tour: the extreme open and close cells.</summary>
    internal sealed class EulerSet {
        private readonly List<ENode> _m;
        private readonly List<ENode> _tops = new();
        private readonly DList.Cell? _minO, _maxO, _minC, _maxC;

        public EulerSet(IEnumerable<ENode> nodes) {
            _m = nodes.Distinct().ToList();
            _m.Sort((a, b) => a == b ? 0 : DList.Less(a.O, b.O) ? -1 : 1);
            if (_m.Count == 0) return;
            _minO = _m[0].O;
            _maxO = _m[^1].O;
            foreach (var n in _m) {
                if (_minC == null || DList.Less(n.C, _minC)) _minC = n.C;
                if (_maxC == null || DList.Less(_maxC, n.C)) _maxC = n.C;
                if (_tops.Count == 0 || !DList.Less(n.O, _tops[^1].C)) _tops.Add(n);   // by open position: ancestors first
            }
        }

        public bool ReachesAll(ENode u) => _minO == null || (DList.Less(u.O, _minO) && DList.Less(_maxC!, u.C));
        public bool ReachedByAll(ENode v) => _minO == null || (DList.Less(_maxO!, v.O) && DList.Less(v.O, _minC!));

        public bool ReachesSome(ENode u) {
            int lo = 0, hi = _m.Count;                                // first member with open after u's open
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(u.O, _m[mid].O)) hi = mid; else lo = mid + 1;
            }
            return lo < _m.Count && DList.Less(_m[lo].O, u.C);
        }

        public bool ReachedBySome(ENode v) {
            int lo = 0, hi = _tops.Count;                             // topmost members with open before v's open
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(_tops[mid].O, v.O)) lo = mid + 1; else hi = mid;
            }
            return lo > 0 && DList.Less(v.O, _tops[lo - 1].C);
        }
    }

    /// <summary>
    /// Pre- and post-order numbers, recomputed lazily: an insertion only marks them stale; the next query
    /// recomputes all of them with one traversal, O(n). Nodes are 0..n-1, node 0 is the root.
    /// </summary>
    internal sealed class PrePostNumbers {
        private readonly List<List<int>?> _kids = new() { null };
        private int[] _pre = Array.Empty<int>(), _post = Array.Empty<int>();
        private readonly Stack<(int Node, bool Done)> _stack = new();
        public bool Stale { get; private set; } = true;
        public int Recomputations { get; private set; }

        public void Insert(int parent, int child) {
            while (_kids.Count <= child) _kids.Add(null);
            (_kids[parent] ??= new List<int>()).Add(child);
            Stale = true;
        }

        public void Refresh() {
            int n = _kids.Count;
            if (_pre.Length < n) { _pre = new int[n * 2]; _post = new int[n * 2]; }
            int clock = 0;
            _stack.Push((0, false));
            while (_stack.Count > 0) {
                var (x, done) = _stack.Pop();
                if (done) { _post[x] = clock++; continue; }
                _pre[x] = clock++;
                _stack.Push((x, true));
                var ks = _kids[x];
                if (ks != null) for (int k = ks.Count - 1; k >= 0; k--) _stack.Push((ks[k], false));
            }
            Stale = false;
            Recomputations++;
        }

        public bool CanReach(int u, int v) {
            if (Stale) Refresh();
            return _pre[u] < _pre[v] && _post[v] < _post[u];
        }

        public NumberSet Set(IEnumerable<int> nodes) {
            if (Stale) Refresh();
            return new NumberSet(_pre, _post, nodes);
        }
    }

    /// <summary>The constructed points of a node set over pre/post numbers (valid until the tree changes).</summary>
    internal sealed class NumberSet {
        private readonly int[] _pre, _post;
        private readonly int[] _keys, _m, _topKeys, _tops;
        private readonly int _minPre, _maxPre, _minPost, _maxPost;
        private readonly bool _empty;

        public NumberSet(int[] pre, int[] post, IEnumerable<int> nodes) {
            _pre = pre;
            _post = post;
            _m = nodes.Distinct().OrderBy(n => pre[n]).ToArray();
            _keys = _m.Select(n => pre[n]).ToArray();
            _empty = _m.Length == 0;
            var tops = new List<int>();
            if (!_empty) {
                _minPre = _keys[0];
                _maxPre = _keys[^1];
                _minPost = _m.Min(n => post[n]);
                _maxPost = _m.Max(n => post[n]);
                foreach (var n in _m)
                    if (tops.Count == 0 || post[n] > post[tops[^1]]) tops.Add(n);
            }
            _tops = tops.ToArray();
            _topKeys = _tops.Select(n => pre[n]).ToArray();
        }

        public bool ReachesAll(int u) => _empty || (_pre[u] < _minPre && _maxPost < _post[u]);
        public bool ReachedByAll(int v) => _empty || (_maxPre < _pre[v] && _post[v] < _minPost);

        public bool ReachesSome(int u) {
            int i = UpperBound(_keys, _pre[u]);
            return i < _m.Length && _post[_m[i]] < _post[u];
        }

        public bool ReachedBySome(int v) {
            int i = LowerBound(_topKeys, _pre[v]);
            return i > 0 && _post[v] < _post[_tops[i - 1]];
        }

        private static int UpperBound(int[] a, int x) {
            int lo = 0, hi = a.Length;
            while (lo < hi) { int mid = (lo + hi) / 2; if (a[mid] <= x) lo = mid + 1; else hi = mid; }
            return lo;
        }

        private static int LowerBound(int[] a, int x) {
            int lo = 0, hi = a.Length;
            while (lo < hi) { int mid = (lo + hi) / 2; if (a[mid] < x) lo = mid + 1; else hi = mid; }
            return lo;
        }
    }

    internal sealed class ICell {
        internal readonly string? Name;
        internal ICell? Prev, Next;
        internal long Label;
        internal object? Node;
        internal ICell(string? name) { Name = name; }
    }

    /// <summary>Doubly linked list with integer labels in [0, 2^62] (classical order maintenance).</summary>
    internal sealed class IntList : IEnumerable<string> {
        private const long U = 1L << 62;
        private const double Slack = 16.0, Growth = 2.0;       // as in DList
        internal readonly ICell First = new("["), Last = new("]");
        public long RenumberCount { get; private set; }
        public long RenumberMoved { get; private set; }

        private readonly int _msd;

        /// <summary>msd 0: the midpoint; 2 or 10: the left neighbor plus half the gap rounded at its most significant digit in that base.</summary>
        public IntList(int msd = 0) {
            _msd = msd;
            First.Next = Last;
            Last.Prev = First;
            Last.Label = U;
        }

        internal ICell InsertNewAfter(string? name, ICell anchor) {
            var cell = new ICell(name);
            var nxt = anchor.Next!;
            cell.Prev = anchor;
            cell.Next = nxt;
            anchor.Next = cell;
            nxt.Prev = cell;
            long g = nxt.Label - anchor.Label;
            if (g >= 2) {
                long x = anchor.Label + (_msd > 0 ? RoundMsd(g >> 1, _msd) : g >> 1);
                if (!(anchor.Label < x && x < nxt.Label)) x = anchor.Label + (g >> 1);
                cell.Label = x;
            } else {
                Rebalance(cell);
            }
            return cell;
        }

        /// <summary>half (> 0) rounded half up at its most significant digit in the given base.</summary>
        private static long RoundMsd(long half, int b) {
            long s = 1;
            while (s <= half / b) s *= b;
            return (half + s / 2) / s * s;
        }

        private void Rebalance(ICell cell) {
            ICell lo = cell, hi = cell, left, right;
            long m = 1, room;
            int k = 1;
            double need = Slack;
            while (true) {
                for (int s = 0; s < k; s++) {
                    if (lo.Prev != First) { lo = lo.Prev!; m++; }
                    if (hi.Next != Last) { hi = hi.Next!; m++; }
                }
                left = lo.Prev!;
                right = hi.Next!;
                room = right.Label - left.Label - 1;
                if (room >= m * need || (left == First && right == Last)) break;
                k *= 2;
                need *= Growth;
            }
            if (room < m) throw new OverflowException("the label universe is full");
            var c = lo;
            for (long j = 0; j < m; j++) {
                c.Label = left.Label + (long)((Int128)(j + 1) * (room + 1) / (m + 1));
                c = c.Next!;
            }
            RenumberCount++;
            RenumberMoved += m;
        }

        public IEnumerator<string> GetEnumerator() {
            for (var c = First.Next!; c != Last; c = c.Next!)
                if (c.Name != null) yield return c.Name;
        }

        System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() => GetEnumerator();

        /// <summary>For tests: true if labels strictly increase from SOURCE to SINK.</summary>
        public bool LabelsStrictlyIncrease() {
            for (var c = First; c.Next != null; c = c.Next)
                if (c.Label >= c.Next.Label) return false;
            return true;
        }
    }

    internal sealed class ENodeInt {
        public readonly string Name;
        internal readonly EulerTourInt Owner;
        internal ICell O = null!, C = null!;
        public ENodeInt(string name, EulerTourInt owner) { Name = name; Owner = owner; }
    }

    /// <summary>The Euler tour of EulerTour on an IntList: integer positions instead of rational ones.</summary>
    internal sealed class EulerTourInt {
        private readonly IntList _q;
        public EulerTourInt(int msd = 0) { _q = new IntList(msd); }
        private readonly Dictionary<string, ENodeInt> _nodes = new();
        public ENodeInt? Root;

        public IntList List => _q;
        public ENodeInt GetNode(string name) => _nodes[name];

        private ENodeInt New(string name, ICell after) {
            var n = new ENodeInt(name, this);
            n.O = _q.InsertNewAfter(name, after);
            n.C = _q.InsertNewAfter(null, n.O);
            n.O.Node = n.C.Node = n;
            _nodes[name] = n;
            return n;
        }

        public ENodeInt Insert(string parent, string child) {
            if (Root == null) Root = New(parent, _q.First);
            return Insert(_nodes[parent], child);
        }

        public ENodeInt Insert(ENodeInt parent, string child) {
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            return New(child, parent.C.Prev!);
        }

        public bool CanReach(ENodeInt u, ENodeInt v) =>
            u.Owner == this && v.Owner == this && u.O.Label < v.O.Label && v.O.Label < u.C.Label;

        public bool CanReach(string u, string v) =>
            _nodes.TryGetValue(u, out var a) && _nodes.TryGetValue(v, out var b) && CanReach(a, b);
    }

    internal sealed class NCell<T> where T : struct, INumber<T> {
        internal readonly string? Name;
        internal NCell<T>? Prev, Next;
        internal T Label;
        internal object? Node;
        internal NCell(string? name) { Name = name; }
    }

    /// <summary>Doubly linked list with floating-point positions (double or decimal); SOURCE and SINK act as -inf and +inf.</summary>
    internal sealed class NumList<T> : IEnumerable<string> where T : struct, INumber<T> {
        private const double Slack = 16.0, Growth = 2.0;        // as in DList
        private static readonly bool IsDecimal = typeof(T) == typeof(decimal);
        private static readonly T Two = T.CreateChecked(2);
        internal readonly NCell<T> First = new("["), Last = new("]");
        public long RenumberCount { get; private set; }
        public long RenumberMoved { get; private set; }

        private readonly int _msd;

        /// <summary>msd 0: the midpoint; 2 or 10: the rule of List.cs in that base; -1 (default): the midpoint for double, base 10 for decimal.</summary>
        public NumList(int msd = -1) {
            _msd = msd >= 0 ? msd : IsDecimal ? 10 : 0;
            if (IsDecimal && _msd != 0 && _msd != 10) throw new ArgumentException("decimal positions: msd 0 or 10");
            First.Next = Last;
            Last.Prev = First;
        }

        internal NCell<T> InsertNewAfter(string? name, NCell<T> anchor) {
            var cell = new NCell<T>(name);
            NCell<T> a = anchor, b = anchor.Next!;
            cell.Prev = a;
            cell.Next = b;
            a.Next = cell;
            b.Prev = cell;
            if (a == First) cell.Label = b == Last ? T.Zero : b.Label - T.One;
            else if (b == Last) cell.Label = a.Label + T.One;
            else if (Between(a.Label, b.Label, _msd) is T x) cell.Label = x;
            else Rebalance(cell);
            return cell;
        }

        private static readonly decimal[] Pow10 = Enumerable.Range(-28, 57).Select(e => e < 0 ? 1m / Pow(-e) : Pow(e)).ToArray();
        private static decimal Pow(int e) { decimal r = 1m; for (int i = 0; i < e; i++) r *= 10m; return r; }

        /// <summary>10^e for the most significant digit of x > 0 (e between -28 and 28).</summary>
        private static decimal MsdScale(decimal x) {
            int e = Math.Clamp((int)Math.Floor(Math.Log10((double)x)), -28, 28);
            while (e > -28 && Pow10[e + 28] > x) e--;
            while (e < 28 && Pow10[e + 29] <= x) e++;
            return Pow10[e + 28];
        }

        /// <summary>A position strictly between lo and hi, or null.</summary>
        private static T? Between(T lo, T hi, int msd) {
            if (msd > 0 && !IsDecimal) {
                double l = Unsafe.As<T, double>(ref lo), h = Unsafe.As<T, double>(ref hi);
                double half = (h - l) / 2;
                if (half > 0) {
                    double s = Math.Pow(msd, Math.Floor(Math.Log(half, msd)));   // most significant digit of half, by its logarithm
                    if (s * msd <= half) s *= msd;
                    else if (s > half) s /= msd;
                    if (s > 0) {
                        double x = l + Math.Round(half / s, MidpointRounding.AwayFromZero) * s;
                        if (l < x && x < h) return Unsafe.As<double, T>(ref x);
                    }
                }
            }
            if (msd > 0 && IsDecimal) {
                decimal l = Unsafe.As<T, decimal>(ref lo), h = Unsafe.As<T, decimal>(ref hi);
                decimal half = (h - l) / 2;
                if (half > 0) {
                    decimal s = MsdScale(half);                   // half the gap, rounded at its most significant digit (List.cs: Middle)
                    decimal x = l + Math.Round(half / s, MidpointRounding.AwayFromZero) * s;
                    if (l < x && x < h) return Unsafe.As<decimal, T>(ref x);
                }
            }
            T mid = (lo + hi) / Two;
            return lo < mid && mid < hi ? mid : null;
        }

        private void Rebalance(NCell<T> cell) {
            NCell<T> lo = cell, hi = cell, left, right;
            int m = 1, k = 1;
            double need = Slack;
            T[] labels;
            while (true) {
                for (int s = 0; s < k; s++) {
                    if (lo.Prev != First) { lo = lo.Prev!; m++; }
                    if (hi.Next != Last) { hi = hi.Next!; m++; }
                }
                left = lo.Prev!;
                right = hi.Next!;
                labels = new T[m];
                if (left == First && right == Last) {
                    for (int j = 0; j < m; j++) labels[j] = T.CreateChecked(j - m / 2);
                    break;
                }
                if (left == First) {
                    for (int j = 0; j < m; j++) labels[j] = right.Label - T.CreateChecked(m - j);
                    break;
                }
                if (right == Last) {
                    for (int j = 0; j < m; j++) labels[j] = left.Label + T.CreateChecked(j + 1);
                    break;
                }
                T step = (right.Label - left.Label) / T.CreateChecked(m + 1);
                if (IsDecimal && _msd > 0 && step > T.Zero) {     // short positions after respacing too
                    decimal st = Unsafe.As<T, decimal>(ref step), sc = MsdScale(st);
                    decimal cut = Math.Floor(st / sc) * sc;
                    step = Unsafe.As<decimal, T>(ref cut);
                }
                T tiny = step / T.CreateChecked(need);
                if (left.Label + tiny > left.Label && right.Label - tiny < right.Label) {
                    bool ok = true;
                    T prev = left.Label;
                    for (int j = 0; j < m && ok; j++) {
                        labels[j] = left.Label + step * T.CreateChecked(j + 1);
                        ok = prev < labels[j];
                        prev = labels[j];
                    }
                    if (ok && prev < right.Label) break;
                }
                k *= 2;
                need *= Growth;
            }
            var c = lo;
            foreach (var x in labels) {
                c.Label = x;
                c = c.Next!;
            }
            RenumberCount++;
            RenumberMoved += m;
        }

        public IEnumerator<string> GetEnumerator() {
            for (var c = First.Next!; c != Last; c = c.Next!)
                if (c.Name != null) yield return c.Name;
        }

        System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() => GetEnumerator();

        /// <summary>For tests: true if positions strictly increase between SOURCE and SINK.</summary>
        public bool LabelsStrictlyIncrease() {
            for (var c = First.Next!; c.Next != Last; c = c.Next!)
                if (!(c.Label < c.Next!.Label)) return false;
            return true;
        }
    }

    internal sealed class ENodeNum<T> where T : struct, INumber<T> {
        public readonly string Name;
        internal readonly EulerTourNum<T> Owner;
        internal NCell<T> O = null!, C = null!;
        public ENodeNum(string name, EulerTourNum<T> owner) { Name = name; Owner = owner; }
    }

    /// <summary>The Euler tour of EulerTour on a NumList: double or decimal positions.</summary>
    internal sealed class EulerTourNum<T> where T : struct, INumber<T> {
        private readonly NumList<T> _q;
        public EulerTourNum(int msd = -1) { _q = new NumList<T>(msd); }
        private readonly Dictionary<string, ENodeNum<T>> _nodes = new();
        public ENodeNum<T>? Root;

        public NumList<T> List => _q;
        public ENodeNum<T> GetNode(string name) => _nodes[name];

        private ENodeNum<T> New(string name, NCell<T> after) {
            var n = new ENodeNum<T>(name, this);
            n.O = _q.InsertNewAfter(name, after);
            n.C = _q.InsertNewAfter(null, n.O);
            n.O.Node = n.C.Node = n;
            _nodes[name] = n;
            return n;
        }

        public ENodeNum<T> Insert(string parent, string child) {
            if (Root == null) Root = New(parent, _q.First);
            return Insert(_nodes[parent], child);
        }

        public ENodeNum<T> Insert(ENodeNum<T> parent, string child) {
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            return New(child, parent.C.Prev!);
        }

        public bool CanReach(ENodeNum<T> u, ENodeNum<T> v) =>
            u.Owner == this && v.Owner == this && u.O.Label < v.O.Label && v.O.Label < u.C.Label;

        public bool CanReach(string u, string v) =>
            _nodes.TryGetValue(u, out var a) && _nodes.TryGetValue(v, out var b) && CanReach(a, b);
    }
}
