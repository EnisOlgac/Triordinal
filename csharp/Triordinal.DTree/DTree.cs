using Triordinal;

namespace DirectedTrees {

    /// <summary>
    /// Handle of a vertex in a <see cref="DTree"/>. Valid while the vertex is in its tree.
    /// </summary>
    public sealed class DNode {
        internal DNode(string name, DTree owner) {
            Name = name;
            Owner = owner;
        }

        public string Name { get; }

        internal DTree? Owner;                  // null once the vertex has been removed
        internal DNode? Up;                     // parent; null for the root
        internal Kid? KH;                       // kids list, read left to right (LR) from here
        internal Kid? KT;                       // kids list, read right to left (RL) from here
        internal Kid? H;                        // this vertex's cell in its parent's kids list
        internal DList.Cell C = null!;          // this vertex's cell in Q1
        internal Run? R;                        // its vertical run; null: a run of its own

        /// <summary>The parent; null for the root.</summary>
        public DNode? Parent => Up;

        /// <summary>The kids, left to right (a copy).</summary>
        public IReadOnlyList<DNode> Children {
            get {
                var list = new List<DNode>();
                for (var k = KH; k != null; k = k.Next) list.Add(k.Node);
                return list;
            }
        }

        /// <summary>False once the vertex has been deleted from its tree.</summary>
        public bool IsInTree => Owner != null;

        public override string ToString() => Name;
    }

    /// <summary>A cell of a kids list; it represents one kid.</summary>
    internal sealed class Kid {
        internal Kid? Prev, Next;
        internal readonly DNode Node;
        internal Kid(DNode node) { Node = node; }
    }

    /// <summary>A vertical run (a sequence of only kids), shared by its members.</summary>
    internal sealed class Run {
        internal DNode Top;
        internal int Size;
        internal Run(DNode top, int size) { Top = top; Size = size; }
    }

    /// <summary>
    /// Single-rooted directed tree on one projection, with its structure kept in the vertices
    /// (DTree 3.0; design by Enis Olgac). Ported from the Python reference triordinal.dtree.core.
    /// </summary>
    /// <remarks>
    /// <para>A vertex keeps its parent, its kids list (read LR from one end, RL from the other), its
    /// handle in its parent's kids list, and its cell in Q1, the pre-order with kids LR. Positions are
    /// rational (the default) or integer. No second projection and no closing cells are stored.</para>
    /// <para>The block of a vertex in Q1 runs from its own cell to just before its delimiter: its
    /// right sibling, or, when it is the last kid, the delimiter of its parent (SINK above the root).
    /// u reaches v exactly when cell(u) &lt; cell(v) &lt; cell(delimiter(u)). CanReach decides this
    /// as a cascade of local steps: 1 v is not right of u, 2 u has no kids, 3 u's right sibling (or
    /// the root), 4 u's last kid (if it is a leaf, its next cell is u's delimiter), 5 look for the
    /// delimiter, up through the ancestors that are last kids.</para>
    /// <para>Step 5 crosses a sequence of only kids (a vertical run) in one step: the members of a run
    /// share one run object that knows the run's top. A run is cut where a vertex gets a second kid
    /// and joined where a vertex is left with one kid; only the shorter part gets a new run object. A
    /// tree that is nothing but a sequence is a list: use DList for it.</para>
    /// <para>DTree 2.x on two projections remains available as DirectedTrees.TwoLists.DTree.</para>
    /// </remarks>
    public sealed class DTree {
        private readonly Dictionary<string, DNode> _nodes = new();
        private readonly DList _q;
        private DNode? _root;

        /// <summary>Steps taken looking for delimiters (for the benchmarks).</summary>
        public long ClimbSteps;

        /// <summary>Vertices given a new run object by cuts and joins (for the benchmarks).</summary>
        public long RunSteps;

        public DTree(string treeId = "P1", Positions positions = Positions.Rational) {
            TreeId = treeId;
            _q = new DList(treeId + ".Q1", positions);
        }

        public string TreeId { get; }

        /// <summary>The kind of position in Q1: rational (the default) or integer.</summary>
        public Positions Positions => _q.Kind;

        /// <summary>How often a region of Q1 was renumbered.</summary>
        public long RenumberCount => _q.RenumberCount;

        public int Count => _nodes.Count;

        public string? Root => _root?.Name;

        /// <summary>The vertices in Q1 order (pre-order, kids LR).</summary>
        public List<string> Q1 => _q.ToList();

        // -- construction from a description ------------------------------------------------

        /// <summary>
        /// Read the .csx description format: "parent: child1; child2" appends last kids,
        /// "sibling > child1; child2" inserts directly after sibling (in that order),
        /// "sibling &lt; child1; child2" directly before it. Empty lines and lines starting with '#',
        /// "--" or "**" are skipped, "@@" ends the description; any other line without ':', '>' or
        /// '&lt;' throws ArgumentException.
        /// </summary>
        public static DTree FromFile(string path, string? treeId = null, Positions positions = Positions.Rational) {
            var tree = new DTree(treeId ?? System.IO.Path.GetFileNameWithoutExtension(path), positions);
            foreach (var raw in File.ReadLines(path)) {
                var line = raw.Trim().TrimStart('﻿');
                if (line.Length == 0 || line.StartsWith('#') || line.StartsWith("--") || line.StartsWith("**")) continue;
                if (line.StartsWith("@@")) break;
                tree.AddLine(line);
            }
            return tree;
        }

        /// <summary>Apply one line of the description format; returns the new handles.</summary>
        public List<DNode> AddLine(string line) {
            int at = line.IndexOfAny(new[] { ':', '>', '<' });
            if (at < 0) throw new ArgumentException($"no ':', '>' or '<' in '{line}'");
            char op = line[at];
            var anchor = line[..at].Trim();
            var added = new List<DNode>();
            foreach (var part in line[(at + 1)..].Split(';')) {
                var child = part.Trim();
                if (child.Length == 0) continue;
                if (op == ':') added.Add(Insert(anchor, child));
                else if (op == '>') { added.Add(InsertAfter(anchor, child)); anchor = child; }
                else added.Add(InsertBefore(anchor, child));
            }
            return added;
        }

        // -- names and handles -------------------------------------------------------------------

        private static void CheckName(string? name, string paramName) {
            if (name == null) throw new ArgumentNullException(paramName, "a node name must not be null");
            if (name.Length == 0) throw new ArgumentException("a node name must not be empty", paramName);
            if (name == Marker.Source || name == Marker.Sink)
                throw new ArgumentException("SOURCE/SINK markers cannot be tree nodes", paramName);
        }

        private DNode Require(string name) =>
            name != null && _nodes.TryGetValue(name, out var n) ? n
                : throw new KeyNotFoundException($"node '{name}' is not in the tree");

        private DNode Own(DNode node) =>
            node.Owner == this ? node : throw new ArgumentException($"node '{node.Name}' does not belong to this tree");

        /// <summary>Handle of the vertex called name. Throws KeyNotFoundException if absent.</summary>
        public DNode GetNode(string name) => Require(name);

        public bool TryGetNode(string name, [System.Diagnostics.CodeAnalysis.MaybeNullWhen(false)] out DNode node) =>
            _nodes.TryGetValue(name, out node);

        public bool Contains(string name) => name != null && _nodes.ContainsKey(name);

        public bool Contains(DNode node) => node.Owner == this;

        // -- kids lists ------------------------------------------------------------------------------

        private static void LinkKid(DNode p, DNode n, Kid? before) {
            var k = new Kid(n);
            n.H = k;
            n.Up = p;
            if (before == null) {
                k.Prev = p.KT;
                if (p.KT == null) p.KH = k; else p.KT.Next = k;
                p.KT = k;
            } else {
                k.Next = before;
                k.Prev = before.Prev;
                if (before.Prev == null) p.KH = k; else before.Prev.Next = k;
                before.Prev = k;
            }
        }

        private static void UnlinkKid(DNode n) {
            Kid k = n.H!;
            DNode p = n.Up!;
            if (k.Prev == null) p.KH = k.Next; else k.Prev.Next = k.Next;
            if (k.Next == null) p.KT = k.Prev; else k.Next.Prev = k.Prev;
            n.H = null;
        }

        private static bool OnlyKid(Kid k) => k.Prev == null && k.Next == null;

        private static bool HasOneKid(DNode p) => p.KH != null && p.KH == p.KT;

        // -- vertical runs: cut and join from the shorter side -----------------------------------------

        /// <summary>
        /// x, an only kid in its parent's run, is about to get a sibling or to leave: cut the run
        /// between x's parent and x; x becomes the top of the lower part. Only the shorter part gets
        /// a new run object; a part of one vertex needs none.
        /// </summary>
        private void Cut(DNode x) {
            Run r = x.R!;
            DNode top = r.Top;
            DNode a = x.Up!, b = x;
            bool lower;
            while (true) {                                    // walk both parts in lockstep
                if (a == top) { lower = false; break; }
                a = a.Up!;
                var k = b.KH;
                if (k == null || k.Next != null) { lower = true; break; }
                b = k.Node;
            }
            var part = new List<DNode>();
            DNode newTop;
            if (lower) {
                for (var m = x; ; ) {
                    part.Add(m);
                    var k = m.KH;
                    if (k == null || k.Next != null) break;
                    m = k.Node;
                }
                newTop = x;
            } else {
                for (var m = x.Up!; ; m = m.Up!) {
                    part.Add(m);
                    if (m == top) break;
                }
                newTop = top;
                r.Top = x;                                    // the lower part keeps r
            }
            var fresh = part.Count > 1 ? new Run(newTop, part.Count) : null;
            foreach (var m in part) m.R = fresh;
            r.Size -= part.Count;
            if (r.Size == 1) r.Top.R = null;
            RunSteps += part.Count;
        }

        /// <summary>x has just become an only kid: its run (topped by x) joins its parent's run.</summary>
        private void Join(DNode x) {
            DNode p = x.Up!;
            Run lo = x.R ??= new Run(x, 1);
            Run hi = p.R ??= new Run(p, 1);
            if (lo.Size <= hi.Size) {
                for (var m = x; ; ) {
                    m.R = hi;
                    var k = m.KH;
                    if (k == null || k.Next != null) break;
                    m = k.Node;
                }
                hi.Size += lo.Size;
                RunSteps += lo.Size;
            } else {
                DNode top = hi.Top;
                for (var m = p; ; m = m.Up!) {
                    m.R = lo;
                    if (m == top) break;
                }
                lo.Size += hi.Size;
                lo.Top = top;
                RunSteps += hi.Size;
            }
        }

        /// <summary>Link n (a new leaf, or a detached subtree topped by n) as a kid of p.</summary>
        private void Attach(DNode p, DNode n, Kid? before) {
            if (HasOneKid(p)) Cut(p.KH!.Node);                // p's only kid gets a sibling
            LinkKid(p, n, before);
            if (HasOneKid(p)) Join(n);                        // n is p's only kid
        }

        /// <summary>Unlink n (with its subtree) from its parent.</summary>
        private void Detach(DNode n) {
            DNode p = n.Up!;
            if (OnlyKid(n.H!)) Cut(n);
            UnlinkKid(n);
            if (HasOneKid(p)) Join(p.KH!.Node);               // one kid left: it joins p's run
        }

        // -- the delimiter ---------------------------------------------------------------------------

        /// <summary>
        /// The cell just after n's block in Q1: its right sibling's cell, or its parent's delimiter
        /// (a vertical run is crossed in one step), or SINK above the root.
        /// </summary>
        private DList.Cell Delimiter(DNode n) {
            while (true) {
                var h = n.H;
                if (h == null) return _q.LastCell;
                if (h.Next != null) return h.Next.Node.C;
                n = h.Prev == null ? n.R!.Top : n.Up!;
                ClimbSteps++;
            }
        }

        /// <summary>The last cell of n's block in Q1.</summary>
        private DList.Cell End(DNode n) => Delimiter(n).Prev!;

        // -- insertion -------------------------------------------------------------------------------

        private DNode NewNode(string name, DList.Cell anchor) {
            if (_nodes.ContainsKey(name)) throw new ArgumentException($"'{name}' is already in the tree");
            var n = new DNode(name, this) { C = _q.InsertNewAfter(name, anchor) };
            n.C.Node = n;
            _nodes[name] = n;
            return n;
        }

        private DNode ParentFor(string parent, string child) {
            CheckName(child, nameof(child));
            if (_root == null) {
                CheckName(parent, nameof(parent));
                if (parent == child) throw new ArgumentException($"'{child}' cannot be its own child");
                _root = NewNode(parent, _q.FirstCell);
                return _root;
            }
            var p = Require(parent);
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"'{child}' is already in the tree");
            return p;
        }

        private DNode ParentFor(DNode parent, string child) {
            Own(parent);
            CheckName(child, nameof(child));
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"'{child}' is already in the tree");
            return parent;
        }

        /// <summary>Append child as the last kid of parent and return its handle. The first call makes parent the root.</summary>
        public DNode Insert(string parent, string child) => InsertLast(ParentFor(parent, child), child);

        public DNode Insert(DNode parent, string child) => InsertLast(ParentFor(parent, child), child);

        private DNode InsertLast(DNode p, string child) {
            var n = NewNode(child, p.KH == null ? p.C : End(p));
            Attach(p, n, null);
            return n;
        }

        /// <summary>Insert child as the first kid of parent: directly after it in Q1.</summary>
        public DNode InsertFirst(string parent, string child) => InsertFirstUnder(ParentFor(parent, child), child);

        public DNode InsertFirst(DNode parent, string child) => InsertFirstUnder(ParentFor(parent, child), child);

        private DNode InsertFirstUnder(DNode p, string child) {
            var n = NewNode(child, p.C);
            Attach(p, n, p.KH);
            return n;
        }

        private DNode Sibling(DNode s, string child) {
            Own(s);
            CheckName(child, nameof(child));
            if (s.Up == null) throw new InvalidOperationException("the root has no siblings");
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"'{child}' is already in the tree");
            return s;
        }

        /// <summary>Insert child directly before sibling, under the same parent.</summary>
        public DNode InsertBefore(string sibling, string child) => InsertBefore(Require(sibling), child);

        public DNode InsertBefore(DNode sibling, string child) {
            var s = Sibling(sibling, child);
            var n = NewNode(child, s.C.Prev!);
            Attach(s.Up!, n, s.H);
            return n;
        }

        /// <summary>Insert child directly after sibling (after its block in Q1), under the same parent.</summary>
        public DNode InsertAfter(string sibling, string child) => InsertAfter(Require(sibling), child);

        public DNode InsertAfter(DNode sibling, string child) {
            var s = Sibling(sibling, child);
            var n = NewNode(child, End(s));
            Attach(s.Up!, n, s.H!.Next);
            return n;
        }

        // -- changes ---------------------------------------------------------------------------------

        private void Forget(DNode n) {
            _nodes.Remove(n.Name);
            n.Owner = null;
            n.Up = null;
            n.KH = n.KT = n.H = null;
            n.R = null;
        }

        /// <summary>Remove node; its kids take its place among its siblings, in order. The root cannot be deleted.</summary>
        public void Delete(string node) => Delete(Require(node));

        public void Delete(DNode node) {
            var n = Own(node);
            if (n.Up == null) throw new InvalidOperationException("the root cannot be deleted");
            DNode p = n.Up;
            Kid k = n.H!;
            if (OnlyKid(k)) Cut(n);
            if (HasOneKid(n)) Cut(n.KH!.Node);
            if (n.KH == null) {
                UnlinkKid(n);
            } else {
                Kid first = n.KH, last = n.KT!;
                for (var c = first; c != null; c = c.Next) c.Node.Up = p;
                first.Prev = k.Prev;                          // n's kids take n's place
                last.Next = k.Next;
                if (k.Prev == null) p.KH = first; else k.Prev.Next = first;
                if (k.Next == null) p.KT = last; else k.Next.Prev = last;
            }
            if (HasOneKid(p)) Join(p.KH!.Node);
            _q.RemoveCell(n.C);
            Forget(n);
        }

        /// <summary>Remove node and all its descendants; returns their names in Q1 order.</summary>
        public List<string> DeleteSubtree(string node) => DeleteSubtree(Require(node));

        public List<string> DeleteSubtree(DNode node) {
            var n = Own(node);
            if (n.Up == null) throw new InvalidOperationException("the root cannot be deleted");
            var cells = _q.CutBlockCells(n.C, End(n), forget: true);
            Detach(n);
            var names = new List<string>(cells.Count);
            foreach (var c in cells) {
                var v = (DNode)c.Node!;
                names.Add(v.Name);
                Forget(v);
            }
            return names;
        }

        /// <summary>Move the subtree of subtreeRoot under newParent, as its last kid.</summary>
        public void CutNPaste(string subtreeRoot, string newParent) => CutNPaste(Require(subtreeRoot), Require(newParent));

        public void CutNPaste(DNode subtreeRoot, DNode newParent) {
            var u = Own(subtreeRoot);
            var p = Own(newParent);
            if (u.Up == null) throw new InvalidOperationException("the root cannot be moved");
            if (u == p || Reach(u, p)) throw new InvalidOperationException("newParent lies inside the subtree being moved");
            var block = _q.CutBlockCells(u.C, End(u), forget: false);
            Detach(u);
            _q.PasteCellsAfter(block, p.KH == null ? p.C : End(p));
            Attach(p, u, null);
        }

        // -- queries ---------------------------------------------------------------------------------

        /// <summary>u reaches v (u is a proper ancestor of v). Irreflexive.</summary>
        public bool CanReach(string u, string v) => Reach(Require(u), Require(v));

        public bool CanReach(DNode u, DNode v) => Reach(Own(u), Own(v));

        public bool CanNotReach(string u, string v) => !CanReach(u, v);

        public bool CanNotReach(DNode u, DNode v) => !CanReach(u, v);

        public bool IsAncestor(string u, string v) => CanReach(u, v);

        public bool IsAncestor(DNode u, DNode v) => CanReach(u, v);

        public bool IsDescendant(string u, string v) => CanReach(v, u);

        public bool IsDescendant(DNode u, DNode v) => CanReach(v, u);

        /// <summary>The cascade: 1 v is not right of u, 2 u has no kids, 3 u's right sibling (or the
        /// root), 4 u's last kid, 5 look for the delimiter.</summary>
        private bool Reach(DNode u, DNode v) {
            if (!DList.Less(u.C, v.C)) return false;                  // 1
            if (u.KH == null) return false;                           // 2
            var h = u.H;
            if (h == null) return true;                               // 3: the root, its delimiter is SINK
            if (h.Next != null) return DList.Less(v.C, h.Next.Node.C);    // 3: the right sibling
            var last = u.KT!.Node;                                    // 4: u's last kid
            if (!DList.Less(last.C, v.C)) return true;
            if (last.KH == null) return DList.Less(v.C, last.C.Next!);    //    a leaf: its next cell is u's delimiter
            return DList.Less(v.C, Delimiter(u));                     // 5
        }

        public string? GetParent(string node) => Require(node).Up?.Name;

        public List<string> Children(string node) => Require(node).Children.Select(k => k.Name).ToList();

        public bool IsRoot(string node) => Require(node).Up == null;

        public bool IsRoot(DNode node) => Own(node).Up == null;

        public bool IsLeaf(string node) => Require(node).KH == null;

        public bool IsLeaf(DNode node) => Own(node).KH == null;

        public int Depth(string node) => Depth(Require(node));

        public int Depth(DNode node) {
            int d = 0;
            for (var n = Own(node); n.Up != null; n = n.Up) d++;
            return d;
        }

        public List<string> PathToRoot(string node) {
            var path = new List<string>();
            for (DNode? n = Require(node); n != null; n = n.Up) path.Add(n.Name);
            return path;
        }

        /// <summary>node and its descendants, in Q1 order.</summary>
        public List<string> Subtree(string node) => Subtree(Require(node));

        public List<string> Subtree(DNode node) {
            var n = Own(node);
            var list = new List<string>();
            var end = Delimiter(n);
            for (var c = n.C; c != end; c = c.Next!) list.Add(c.Name!);
            return list;
        }

        public int SubtreeSize(string node) => Subtree(node).Count;

        public override string ToString() => _q.ToString();

        // -- and/or queries: constructed nodes, built for the query at hand ---------------------------

        public VMin VMin(IEnumerable<string> nodes) => new(this, nodes.Select(Require));
        public VMin VMin(IEnumerable<DNode> nodes) => new(this, nodes.Select(Own));
        public VMax VMax(IEnumerable<string> nodes) => new(this, nodes.Select(Require));
        public VMax VMax(IEnumerable<DNode> nodes) => new(this, nodes.Select(Own));
        public UMin UMin(IEnumerable<string> nodes) => new(this, nodes.Select(Require));
        public UMin UMin(IEnumerable<DNode> nodes) => new(this, nodes.Select(Own));
        public UMax UMax(IEnumerable<string> nodes) => new(this, nodes.Select(Require));
        public UMax UMax(IEnumerable<DNode> nodes) => new(this, nodes.Select(Own));

        internal DNode Handle(string name) => Require(name);
        internal DNode Handle(DNode node) => Own(node);
        internal DList.Cell DelimiterOf(DNode n) => Delimiter(n);
    }

    /// <summary>
    /// A set S of vertices reduced to what an and/or query needs, at the moment it is built. Built
    /// for the query at hand: after the tree changes, build it again.
    /// </summary>
    public abstract class ConstructedNode {
        private protected readonly DTree Tree;
        private protected readonly DNode[] Ms;            // the members, in Q1 order

        private protected ConstructedNode(DTree tree, IEnumerable<DNode> nodes) {
            Tree = tree;
            var set = new Dictionary<string, DNode>();
            foreach (var n in nodes) set[n.Name] = n;
            if (set.Count == 0) throw new ArgumentException("a constructed node needs at least one member");
            Ms = set.Values.ToArray();
            Array.Sort(Ms, (a, b) => DList.Less(a.C, b.C) ? -1 : DList.Less(b.C, a.C) ? 1 : 0);
        }

        /// <summary>The members in Q1 order.</summary>
        public List<string> Members => Ms.Select(m => m.Name).ToList();

        public int Count => Ms.Length;

        public bool Contains(string node) => Ms.Any(m => m.Name == node);

        /// <summary>How many of items (in Q1 order) lie left of v: a binary search.</summary>
        private protected static int CountBefore(DNode[] items, DNode v) {
            int lo = 0, hi = items.Length;
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(items[mid].C, v.C)) lo = mid + 1; else hi = mid;
            }
            return lo;
        }
    }

    /// <summary>S as the target: does u reach all of S? u lies left of the first member and its delimiter right of the last.</summary>
    public sealed class VMin : ConstructedNode {
        internal VMin(DTree tree, IEnumerable<DNode> nodes) : base(tree, nodes) { }

        public bool ReachesAll(string u) => ReachesAll(Tree.Handle(u));

        public bool ReachesAll(DNode u) {
            u = Tree.Handle(u);
            return DList.Less(u.C, Ms[0].C) && DList.Less(Ms[^1].C, Tree.DelimiterOf(u));
        }
    }

    /// <summary>S as the target: does u reach some of S? The first member after u lies inside u's block.</summary>
    public sealed class VMax : ConstructedNode {
        internal VMax(DTree tree, IEnumerable<DNode> nodes) : base(tree, nodes) { }

        public bool ReachesSome(string u) => ReachesSome(Tree.Handle(u));

        public bool ReachesSome(DNode u) {
            u = Tree.Handle(u);
            int i = CountBefore(Ms, u);
            if (i < Ms.Length && Ms[i] == u) i++;
            return i < Ms.Length && DList.Less(u.C, Ms[i].C) && DList.Less(Ms[i].C, Tree.DelimiterOf(u));
        }
    }

    /// <summary>S as the source: is v reached by all of S? v lies right of the last member and left of the first delimiter.</summary>
    public sealed class UMax : ConstructedNode {
        private readonly DList.Cell _firstDelimiter;

        internal UMax(DTree tree, IEnumerable<DNode> nodes) : base(tree, nodes) {
            DList.Cell? first = null;
            foreach (var m in Ms) {
                var d = tree.DelimiterOf(m);
                if (first == null || DList.Less(d, first)) first = d;
            }
            _firstDelimiter = first!;
        }

        public bool ReachedByAll(string v) => ReachedByAll(Tree.Handle(v));

        public bool ReachedByAll(DNode v) {
            v = Tree.Handle(v);
            return DList.Less(Ms[^1].C, v.C) && DList.Less(v.C, _firstDelimiter);
        }
    }

    /// <summary>
    /// S as the source: is v reached by some of S? Only the topmost members count (those with no
    /// ancestor in S); their blocks are disjoint, so the last one left of v decides.
    /// </summary>
    public sealed class UMin : ConstructedNode {
        private readonly DNode[] _tops;
        private readonly DList.Cell[] _ends;

        internal UMin(DTree tree, IEnumerable<DNode> nodes) : base(tree, nodes) {
            var tops = new List<DNode>();
            var ends = new List<DList.Cell>();
            DList.Cell? end = null;
            foreach (var m in Ms) {
                if (end == null || !DList.Less(m.C, end)) {
                    end = tree.DelimiterOf(m);
                    tops.Add(m);
                    ends.Add(end);
                }
            }
            _tops = tops.ToArray();
            _ends = ends.ToArray();
        }

        /// <summary>The topmost member that reaches v, or null.</summary>
        public string? Covering(string v) => Covering(Tree.Handle(v));

        public string? Covering(DNode v) {
            v = Tree.Handle(v);
            int i = CountBefore(_tops, v);
            if (i == 0) return null;
            return DList.Less(v.C, _ends[i - 1]) ? _tops[i - 1].Name : null;
        }

        public bool ReachedBySome(string v) => Covering(v) != null;

        public bool ReachedBySome(DNode v) => Covering(v) != null;
    }
}
