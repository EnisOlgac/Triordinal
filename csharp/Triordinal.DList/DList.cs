using System.Collections;

namespace Triordinal {

    /// <summary>Names of the two symbolic markers that bracket every projection.</summary>
    public static class Marker {
        public const string Source = "[";
        public const string Sink = "]";
    }

    /// <summary>
    /// Doubly linked list of node names with rational positions (O(1) precedence test).
    /// </summary>
    /// <remarks>
    /// A position is a fraction Num/Den. A new node gets the mediant (a+c)/(b+d) of its
    /// neighbors a/b and c/d, which always lies strictly between them; SOURCE and SINK act
    /// as -1/0 and +1/0. Nothing else moves. Only when a denominator would exceed 2^40 is a
    /// small surrounding region renumbered with simple fractions k/2^20, larger regions being
    /// required to be sparser (as in Bender et al., ESA 2002). Rational positions were Enis
    /// Olgac's idea; this C# version follows the Python reference implementation (1.1.0).
    /// Positions are 64-bit (Num, Den) pairs compared with 128-bit products. A numerator grows
    /// with value times denominator, and values grow with every insertion at an end of the list
    /// (deletions never shrink them), so a region is also renumbered when a numerator would
    /// exceed 2^61. Every mediant is then the sum of two numerators below 2^61 and cannot
    /// overflow, and a cell is linked only after its position has been computed.
    /// </remarks>
    public sealed class DList : IEnumerable<string> {
        private const long Q = 1L << 20;        // denominator used when a region is renumbered
        private const long Limit = 1L << 40;    // renumber when a denominator would exceed this
        private const long NumLimit = 1L << 61; // ... or a numerator; two such numerators sum below 2^62
        private const double Slack = 16.0;      // minimum spacing (in 1/Q) after renumbering
        private const double Growth = 2.0;      // each doubling of the region raises the spacing

        internal sealed class Cell {
            internal readonly string Name;
            internal Cell? Prev;
            internal Cell? Next;
            internal long Num;
            internal long Den = 1;
            internal object? Node;              // the node owning this cell (a DTree or DGraph node handle)
            internal Cell(string name) { Name = name; }
        }

        private readonly Dictionary<string, Cell> _cells = new();
        private readonly Cell _first;
        private readonly Cell _last;

        public DList(string name) {
            Name = name;
            _first = New(Marker.Source);
            _last = New(Marker.Sink);
            _first.Next = _last;
            _last.Prev = _first;
            _first.Num = -1; _first.Den = 0;    // -infinity
            _last.Num = 1; _last.Den = 0;       // +infinity
        }

        public string Name { get; }

        /// <summary>How often a region was renumbered.</summary>
        public long RenumberCount { get; private set; }

        /// <summary>How many positions were changed by renumbering in total.</summary>
        public long RenumberMoved { get; private set; }

        /// <summary>Number of nodes, without the markers.</summary>
        public int Count => _cells.Count - 2;

        public string Source => _first.Name;
        public string Sink => _last.Name;

        // -- internals ---------------------------------------------------------

        private Cell New(string name) {
            var cell = new Cell(name);
            _cells[name] = cell;
            return cell;
        }

        private Cell Get(string name) =>
            _cells.TryGetValue(name, out var c) ? c : throw new KeyNotFoundException($"'{name}' is not in {Name}");

        /// <summary>x lies strictly left of y.</summary>
        private static bool Lt(Cell x, Cell y) {
            if (x.Den != 0 && y.Den != 0) return (Int128)x.Num * y.Den < (Int128)y.Num * x.Den;
            if (x.Den == 0 && y.Den == 0) return x.Num < y.Num;
            long xi = x.Den == 0 ? x.Num : 0, yi = y.Den == 0 ? y.Num : 0;
            return xi < yi;
        }

        private static long FloorMulDiv(long num, long q, long den) {
            Int128 a = (Int128)num * q;
            Int128 r = a / den;
            if (a % den != 0 && a < 0) r -= 1;      // den > 0
            return checked((long)r);
        }

        private static long CeilMulDiv(long num, long q, long den) => -FloorMulDiv(-num, q, den);

        private void LinkAfter(Cell cell, Cell prev) {
            var nxt = prev.Next!;
            long num, den;
            if (prev == _first && nxt == _last) {    // first node of an empty list
                num = 0; den = 1;
            } else {
                // Mediant of the neighbors. Next to SOURCE (-1/0) or SINK (+1/0) this steps by one
                // whole unit, so a list can grow at either end without renumbering. Computed
                // before the cell is linked: |Num| <= 2^61 and Den <= 2^40 for every linked cell,
                // so the sums cannot overflow; checked all the same.
                checked {
                    num = prev.Num + nxt.Num;
                    den = prev.Den + nxt.Den;
                }
            }
            cell.Prev = prev;
            cell.Next = nxt;
            prev.Next = cell;
            nxt.Prev = cell;
            cell.Num = num;
            cell.Den = den;
            if (den > Limit || num > NumLimit || num < -NumLimit) Rebalance(cell);
        }

        private void Unlink(Cell cell) {
            cell.Prev!.Next = cell.Next;
            cell.Next!.Prev = cell.Prev;
            cell.Prev = cell.Next = null;
        }

        /// <summary>Renumber the smallest region around cell that has room, using fractions k/Q.</summary>
        private void Rebalance(Cell cell) {
            Cell lo = cell, hi = cell;
            int m = 1, k = 1;
            double need = Slack;
            long[] ks;
            while (true) {
                for (int s = 0; s < k; s++) {
                    if (lo.Prev != _first) { lo = lo.Prev!; m++; }
                    if (hi.Next != _last) { hi = hi.Next!; m++; }
                }
                Cell left = lo.Prev!, right = hi.Next!;
                ks = new long[m];
                if (left == _first && right == _last) {
                    for (int j = 0; j < m; j++) ks[j] = checked((j - m / 2) * Q);
                    break;
                }
                if (left == _first) {
                    long top = CeilMulDiv(right.Num, Q, right.Den);
                    for (int j = 0; j < m; j++) ks[j] = checked(top - (m - j) * Q);
                    break;
                }
                if (right == _last) {
                    long bottom = FloorMulDiv(left.Num, Q, left.Den);
                    for (int j = 0; j < m; j++) ks[j] = checked(bottom + (j + 1) * Q);
                    break;
                }
                long lo_k = FloorMulDiv(left.Num, Q, left.Den);
                long hi_k = CeilMulDiv(right.Num, Q, right.Den);
                long room = hi_k - lo_k - 1;    // integers k with left < k/Q < right
                if (room >= m * need) {
                    for (int j = 0; j < m; j++)
                        ks[j] = lo_k + (long)((Int128)(j + 1) * (room + 1) / (m + 1));
                    break;
                }
                // Larger regions must be sparser before they are accepted, so a renumbered
                // region keeps spare room and the next overflow nearby stays local.
                k *= 2;
                need *= Growth;
            }
            var c = lo;
            foreach (var kv in ks) {
                c.Num = kv;
                c.Den = Q;
                c = c.Next!;
            }
            RenumberCount++;
            RenumberMoved += m;
        }

        private Cell CellFor(string name) {
            if (name == Marker.Source || name == Marker.Sink)
                throw new ArgumentException($"the markers {Marker.Source} and {Marker.Sink} cannot be inserted or moved", nameof(name));
            if (_cells.TryGetValue(name, out var cell)) {
                Unlink(cell);           // an existing node is moved
                return cell;
            }
            return New(name);
        }

        // -- cell-level operations for the node handles of DTree and DGraph ------------------------

        internal Cell FirstCell => _first;
        internal Cell LastCell => _last;
        internal Cell CellOf(string name) => Get(name);

        /// <summary>x lies strictly left of y (exact rational comparison).</summary>
        internal static bool Less(Cell x, Cell y) {
            if (x.Den != 0 && y.Den != 0) return (Int128)x.Num * y.Den < (Int128)y.Num * x.Den;
            return Lt(x, y);
        }

        /// <summary>Create a cell for a new name directly after anchor.</summary>
        internal Cell InsertNewAfter(string name, Cell anchor) {
            if (_cells.ContainsKey(name)) throw new ArgumentException($"'{name}' is already in {Name}");
            var cell = New(name);
            LinkAfter(cell, anchor);
            return cell;
        }

        internal void RemoveCell(Cell cell) {
            Unlink(cell);
            _cells.Remove(cell.Name);
        }

        /// <summary>Remove the contiguous block a..b and return its cells in order.</summary>
        internal List<Cell> CutBlockCells(Cell a, Cell b) {
            var cells = new List<Cell>();
            for (var c = a; ; c = c.Next!) {
                cells.Add(c);
                if (c == b) break;
            }
            a.Prev!.Next = b.Next;
            b.Next!.Prev = a.Prev;
            a.Prev = null;
            b.Next = null;
            foreach (var c in cells) _cells.Remove(c.Name);
            return cells;
        }

        /// <summary>Re-insert cut cells in order directly after anchor (new positions are assigned).</summary>
        internal void PasteCellsAfter(List<Cell> cells, Cell anchor) {
            foreach (var c in cells) {
                _cells[c.Name] = c;
                LinkAfter(c, anchor);
                anchor = c;
            }
        }

        // -- public (names follow List.cs) ---------------------------------------

        public bool Contains(string name) => _cells.ContainsKey(name);
        public bool IsAllocated(string name) => _cells.ContainsKey(name);
        public bool IsNotAllocated(string name) => !_cells.ContainsKey(name);

        /// <summary>Position of name as (Num, Den); SOURCE/SINK have Den 0. Null if absent.</summary>
        public (long Num, long Den)? Index(string name) =>
            _cells.TryGetValue(name, out var c) ? (c.Num, c.Den) : null;

        /// <summary>Position of name as a double (for display; comparisons use exact arithmetic).</summary>
        public double IndexValue(string name) {
            var c = Get(name);
            if (c.Den == 0) return c.Num > 0 ? double.PositiveInfinity : double.NegativeInfinity;
            return (double)c.Num / c.Den;
        }

        public string? Next(string name) => Get(name).Next?.Name;
        public string? Prev(string name) => Get(name).Prev?.Name;

        public bool IsLeftOf(string v, string u) => Lt(Get(v), Get(u));
        public bool IsSelfOrLeftOf(string v, string u) => v == u || Lt(Get(v), Get(u));
        public bool IsRightOf(string v, string u) => Lt(Get(u), Get(v));
        public bool IsSelfOrRightOf(string v, string u) => v == u || Lt(Get(u), Get(v));

        /// <summary>Strict order: u lies left of v (same as IsLeftOf).</summary>
        public bool Precedes(string u, string v) {
            var x = Get(u);
            var y = Get(v);
            if (x.Den != 0 && y.Den != 0) return (Int128)x.Num * y.Den < (Int128)y.Num * x.Den;
            return Lt(x, y);
        }

        /// <summary>Place name directly after anchor; moves it if already present (List.cs: InsAfter).</summary>
        public void InsertAfter(string name, string anchor) {
            if (name == Marker.Source || name == Marker.Sink)
                throw new ArgumentException($"the markers {Marker.Source} and {Marker.Sink} cannot be inserted or moved", nameof(name));
            if (name == anchor) return;
            if (anchor == Marker.Sink) { InsertBefore(name, Marker.Sink); return; }
            var a = Get(anchor);
            if (a.Next != null && a.Next.Name == name) return;
            var cell = CellFor(name);
            LinkAfter(cell, Get(anchor));
        }

        /// <summary>Place name directly before anchor; moves it if already present (List.cs: InsBefore).</summary>
        public void InsertBefore(string name, string anchor) {
            if (name == Marker.Source || name == Marker.Sink)
                throw new ArgumentException($"the markers {Marker.Source} and {Marker.Sink} cannot be inserted or moved", nameof(name));
            if (name == anchor) return;
            if (anchor == Marker.Source) { InsertAfter(name, Marker.Source); return; }
            var a = Get(anchor);
            if (a.Prev != null && a.Prev.Name == name) return;
            var cell = CellFor(name);
            LinkAfter(cell, Get(anchor).Prev!);
        }

        public void Remove(string name) {
            var cell = Get(name);
            if (cell == _first || cell == _last) throw new InvalidOperationException("markers cannot be removed");
            Unlink(cell);
            _cells.Remove(name);
        }

        /// <summary>Remove the contiguous block first..last and return its names in order.</summary>
        public List<string> CutBlock(string first, string last) {
            Cell a = Get(first), b = Get(last);
            var names = new List<string>();
            for (var cell = a; ; cell = cell.Next!) {
                names.Add(cell.Name);
                if (cell == b) break;
            }
            a.Prev!.Next = b.Next;
            b.Next!.Prev = a.Prev;
            foreach (var n in names) _cells.Remove(n);
            return names;
        }

        public void PasteBlockAfter(IEnumerable<string> names, string anchor) {
            foreach (var n in names) {
                InsertAfter(n, anchor);
                anchor = n;
            }
        }

        /// <summary>True if both lists hold the same nodes in the same order (List.cs: IsSameAs).</summary>
        public bool IsSameAs(DList other) => this.SequenceEqual(other);

        public IEnumerator<string> GetEnumerator() {
            for (var c = _first.Next!; c != _last; c = c.Next!) yield return c.Name;
        }

        IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();

        public List<string> ToList(bool withMarkers = false) {
            var list = new List<string>();
            if (withMarkers) list.Add(Marker.Source);
            list.AddRange(this);
            if (withMarkers) list.Add(Marker.Sink);
            return list;
        }

        public override string ToString() => $"{Name}: [{string.Join(", ", this)}]";

        /// <summary>For tests: true if positions strictly increase from SOURCE to SINK.</summary>
        public bool PositionsStrictlyIncrease() {
            for (var c = _first; c.Next != null; c = c.Next)
                if (!Lt(c, c.Next!)) return false;
            return true;
        }

        /// <summary>For tests: the largest denominator in use.</summary>
        public long MaxDenominator() => _cells.Values.Max(c => c.Den);
    }
}
