using System.Collections;
using Triordinal;

namespace DirectedTrees {

    /// <summary>
    /// Handle of a node in a <see cref="DTree"/>. It refers directly to the node's positions in
    /// Q1 and Q2, so reachability tests on handles need no lookup by name.
    /// </summary>
    public sealed class DNode {
        internal DNode(string name, DTree? owner) {
            Name = name;
            Owner = owner;
        }

        public string Name { get; }

        internal DTree? Owner;                  // null once the node has been removed
        internal DNode? Up;                     // parent; the SOURCE sentinel for the root
        internal List<DNode>? Kids;             // children in Q1 order
        internal DList.Cell C1 = null!;         // position in Q1
        internal DList.Cell C2 = null!;         // position in Q2 (null in an EulerTree)
        internal DList.Cell? E1;                // closing cell in Q1 (only while the node has children)
        internal DList.Cell? E2;                // closing cell in Q2 (likewise)

        /// <summary>The parent node; null for the root.</summary>
        public DNode? Parent => Up == null || Up.Owner == null ? null : Up;

        /// <summary>The children in Q1 order (a copy).</summary>
        public IReadOnlyList<DNode> Children => Kids == null ? Array.Empty<DNode>() : Kids.ToArray();

        /// <summary>False once the node has been deleted from its tree.</summary>
        public bool IsInTree => Owner != null;

        public override string ToString() => Name;
    }

    /// <summary>
    /// Read-only view of Q1 or Q2: the nodes in list order, with the list-level checks of DList
    /// (IsLeftOf, Index, Next, ...). Closing cells are not shown. Live: it always reflects the
    /// current tree, which changes only through DTree methods.
    /// </summary>
    public sealed class Projection : IEnumerable<string> {
        private readonly DList _list;

        internal Projection(DList list) { _list = list; }

        public string Name => _list.Name;
        public string Source => Marker.Source;
        public string Sink => Marker.Sink;

        /// <summary>Number of nodes, without the markers.</summary>
        public int Count => _list.Count;

        /// <summary>How often a region of the list was renumbered.</summary>
        public long RenumberCount => _list.RenumberCount;

        /// <summary>How many positions renumbering changed in total (closing cells included).</summary>
        public long RenumberMoved => _list.RenumberMoved;

        public bool Contains(string name) => _list.Contains(name);
        public bool IsAllocated(string name) => _list.IsAllocated(name);
        public bool IsNotAllocated(string name) => _list.IsNotAllocated(name);

        /// <summary>Position of name as (Num, Den); SOURCE/SINK have Den 0. Null if absent.</summary>
        public (long Num, long Den)? Index(string name) => _list.Index(name);

        /// <summary>Position of name as a double (for display; comparisons use exact arithmetic).</summary>
        public double IndexValue(string name) => _list.IndexValue(name);

        public string? Next(string name) => _list.Next(name);
        public string? Prev(string name) => _list.Prev(name);
        public bool IsLeftOf(string v, string u) => _list.IsLeftOf(v, u);
        public bool IsSelfOrLeftOf(string v, string u) => _list.IsSelfOrLeftOf(v, u);
        public bool IsRightOf(string v, string u) => _list.IsRightOf(v, u);
        public bool IsSelfOrRightOf(string v, string u) => _list.IsSelfOrRightOf(v, u);
        public bool Precedes(string u, string v) => _list.Precedes(u, v);

        /// <summary>True if both hold the same nodes in the same order.</summary>
        public bool IsSameAs(IEnumerable<string> other) => this.SequenceEqual(other);

        public IEnumerator<string> GetEnumerator() => _list.GetEnumerator();
        IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();

        public List<string> ToList(bool withMarkers = false) => _list.ToList(withMarkers);

        public override string ToString() => _list.ToString();

        /// <summary>For tests: true if positions strictly increase from SOURCE to SINK (closing cells included).</summary>
        public bool PositionsStrictlyIncrease() => _list.PositionsStrictlyIncrease();

        /// <summary>For tests: the largest denominator in use (closing cells included).</summary>
        public long MaxDenominator() => _list.MaxDenominator();
    }

    /// <summary>
    /// Single-rooted directed tree encoded by two linear projections Q1 and Q2.
    /// </summary>
    /// <remarks>
    /// Q1 is the pre-order with children left to right (insertion order); Q2 the pre-order
    /// with siblings right to left. Node u reaches node v if and only if u strictly precedes v
    /// in both Q1 and Q2 (irreflexive: no node reaches itself). A new child is the last child of
    /// its parent in Q1 and the first in Q2, so every change is local to both lists.
    /// A node with children also has a closing cell in each list, an unnamed cell directly after
    /// the last cell of its subtree (the parent's delimiter of the paper): the subtree is the block
    /// from the node to its closing cell, so the end of a block is known without any search.
    /// Every operation checks its arguments before it changes anything, so an operation that
    /// throws leaves the tree as it was.
    /// With strict set, queries about nodes (CanReach, CanNotReach, IsAncestor, IsDescendant,
    /// IsRoot and the queries of constructed nodes) throw for a name that is not in the tree
    /// (KeyNotFoundException) or a handle of a removed node (ArgumentException) instead of
    /// answering false; Contains and SameSubtree are membership tests and never throw.
    /// Every method is available with node names and, for speed, with <see cref="DNode"/>
    /// handles, which refer to their positions directly (the idea of using addresses as ids is
    /// Enis Olgac's, from his original implementation).
    /// Positions are rational by default; Positions.Integer gives integer positions.
    /// Design and API: Enis Olgac. This C# version mirrors the Python reference implementation,
    /// which was written with Claude (Anthropic).
    /// </remarks>
    public class DTree {
        private readonly Dictionary<string, DNode> _nodes = new();
        private readonly DNode _source;         // sentinel: parent of the root
        private readonly DList _q1;
        private readonly DList? _q2;            // null in an EulerTree (Q1 only)
        private readonly Projection? _v2;
        private readonly List<string> _edgeLog = new();
        internal int Reshapes;                  // counts deletions and moves; insertions keep the order of existing nodes
        internal readonly bool Single;          // EulerTree: Q1 only, reachability by blocks
        private readonly bool _int;             // integer positions: compared directly

        public DTree(string treeId = "P1", bool strict = false, Positions positions = Positions.Rational)
            : this(treeId, strict, positions, false) { }

        /// <summary>For EulerTree: one list (Q1 with closing cells) when single is set.</summary>
        private protected DTree(string treeId, bool strict, Positions positions, bool single) {
            TreeId = treeId;
            Strict = strict;
            Single = single;
            _int = positions == Positions.Integer;
            _q1 = new DList(treeId + ".Q1", positions);
            Q1 = new Projection(_q1);
            _source = new DNode(Marker.Source, null) { C1 = _q1.FirstCell };
            if (!single) {
                _q2 = new DList(treeId + ".Q2", positions);
                _v2 = new Projection(_q2);
                _source.C2 = _q2.FirstCell;
            }
        }

        /// <summary>The kind of position in the lists: rational (the default) or integer.</summary>
        public Positions Positions => _q1.Kind;

        public string TreeId { get; }

        /// <summary>Whether queries throw for unknown nodes instead of answering false (set at construction).</summary>
        public bool Strict { get; }

        // -- construction -----------------------------------------------------------

        /// <summary>
        /// Read the format used by the .csx examples: "parent: child1; child2" adds last children,
        /// "sibling > child1; child2" inserts siblings directly after sibling (in that order),
        /// "sibling &lt; child1; child2" directly before it. Empty lines and lines starting with
        /// '#', "--" or "**" are skipped, "@@" ends the description; any other line without ':',
        /// '>' or '&lt;' throws ArgumentException.
        /// </summary>
        public static DTree FromFile(string path, string? treeId = null, bool strict = false, Positions positions = Positions.Rational) {
            var tree = new DTree(treeId ?? System.IO.Path.GetFileNameWithoutExtension(path), strict, positions);
            tree.ReadFile(path);
            return tree;
        }

        private protected void ReadFile(string path) {
            var tree = this;
            foreach (var raw in File.ReadLines(path)) {
                var line = raw.Trim().TrimStart('﻿');
                if (line.Length == 0 || line.StartsWith('#') || line.StartsWith("--") || line.StartsWith("**")) continue;
                if (line.StartsWith("@@")) break;
                tree.AddLine(line);
            }
        }

        /// <summary>
        /// Apply one line of the description format (see FromFile); returns the new handles. The
        /// children are added one by one; if one of them is rejected, those before it remain.
        /// </summary>
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
                else if (op == '>') { added.Add(InsertAfter(anchor, child)); anchor = child; }   // the next one goes after this one
                else added.Add(InsertBefore(anchor, child));
            }
            return added;
        }

        private static void CheckName(string? name, string paramName) {
            if (name == null) throw new ArgumentNullException(paramName, "a node name must not be null");
            if (name.Length == 0) throw new ArgumentException("a node name must not be empty", paramName);
            if (IsMarker(name)) throw new ArgumentException("SOURCE/SINK markers cannot be tree nodes", paramName);
        }

        /// <summary>
        /// Add the edge parent -> child and return the child's handle. The first call makes parent
        /// the root; afterwards parent must already exist and child must not.
        /// </summary>
        public DNode Insert(string parent, string child) {
            CheckName(child, nameof(child));
            DNode p;
            if (_nodes.Count == 0) {
                CheckName(parent, nameof(parent));
                if (parent == child) throw new ArgumentException($"child '{child}' is already in the tree");
                p = MakeRoot(parent);
            } else {
                p = Require(parent);
            }
            return InsertUnder(p, child);
        }

        /// <summary>Add a child under an existing node handle and return the child's handle.</summary>
        public DNode Insert(DNode parent, string child) {
            Own(parent);
            CheckName(child, nameof(child));
            return InsertUnder(parent, child);
        }

        private DNode InsertUnder(DNode p, string child) {
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            Open(p);
            var n = Link(child, p, null, p.E1!.Prev!, p.C2);       // Q1 before p's closing cell, Q2 after p
            _edgeLog.Add($"({p.Name}, {child})");
            return n;
        }

        /// <summary>
        /// Insert child as a sibling directly after sibling (same parent) and return its handle. In Q1
        /// it goes after the end of the sibling's subtree, in Q2 directly before the sibling; no other
        /// node moves. The root has no siblings.
        /// </summary>
        public DNode InsertAfter(string sibling, string child) => InsertAfter(Require(sibling), child);

        public DNode InsertAfter(DNode sibling, string child) {
            var s = CheckSibling(sibling, child);
            var p = s.Up!;
            int i = p.Kids!.IndexOf(s);
            var n = Link(child, p, i + 1, End1(s), Single ? null : s.C2.Prev!);
            _edgeLog.Add($"({s.Name} > {child})");
            return n;
        }

        /// <summary>
        /// Insert child as a sibling directly before sibling (same parent) and return its handle. In Q1
        /// it goes directly before the sibling, in Q2 after the end of the sibling's subtree there
        /// (its closing cell); no other node moves.
        /// </summary>
        public DNode InsertBefore(string sibling, string child) => InsertBefore(Require(sibling), child);

        public DNode InsertBefore(DNode sibling, string child) {
            var s = CheckSibling(sibling, child);
            var p = s.Up!;
            int i = p.Kids!.IndexOf(s);
            var n = Link(child, p, i, s.C1.Prev!, Single ? null : End2(s));
            _edgeLog.Add($"({s.Name} < {child})");
            return n;
        }

        private DNode CheckSibling(DNode sibling, string child) {
            Own(sibling);
            CheckName(child, nameof(child));
            if (sibling.Up == _source) throw new InvalidOperationException("the root has no siblings");
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            return sibling;
        }

        private DNode MakeRoot(string name) {
            var n = new DNode(name, this) {
                C1 = _q1.InsertNewAfter(name, _q1.FirstCell),
                Up = _source,
            };
            n.C1.Node = n;
            if (!Single) {
                n.C2 = _q2!.InsertNewAfter(name, _q2.FirstCell);
                n.C2.Node = n;
            }
            _source.Kids = new List<DNode> { n };
            _nodes[name] = n;
            return n;
        }

        /// <summary>
        /// Create a child of p at position index among p's children (null: last), linked after the
        /// given cells. All checks are done; the name is registered last.
        /// </summary>
        private DNode Link(string name, DNode p, int? index, DList.Cell q1After, DList.Cell? q2After) {
            var n = new DNode(name, this) {
                C1 = _q1.InsertNewAfter(name, q1After),
                Up = p,
            };
            n.C1.Node = n;
            if (!Single) {
                n.C2 = _q2!.InsertNewAfter(name, q2After!);
                n.C2.Node = n;
            }
            var kids = p.Kids ??= new List<DNode>();
            if (index is int i) kids.Insert(i, n); else kids.Add(n);
            _nodes[name] = n;
            return n;
        }

        private static bool IsMarker(string v) => v == Marker.Source || v == Marker.Sink;

        // -- closing cells -----------------------------------------------------------

        /// <summary>Give p its closing cells if it has none: directly after p, as its block is p alone.</summary>
        private void Open(DNode p) {
            if (p.E1 != null) return;
            p.E1 = _q1.InsertNewAfter(null, p.C1);
            p.E1.Node = p;
            if (!Single) {
                p.E2 = _q2!.InsertNewAfter(null, p.C2);
                p.E2.Node = p;
            }
        }

        /// <summary>Remove p's closing cells once p has no children left.</summary>
        private void Close(DNode p) {
            if (p.E1 == null) return;
            _q1.RemoveCell(p.E1);
            if (!Single) _q2!.RemoveCell(p.E2!);
            p.E1 = p.E2 = null;
        }

        private static DList.Cell End1(DNode n) => n.E1 ?? n.C1;
        private static DList.Cell End2(DNode n) => n.E2 ?? n.C2;

        /// <summary>
        /// The node after node in Q1, or null after the last node. Q1 is the display order of a tree
        /// view (parents before children, siblings in insertion order). Passes over the closing cells
        /// of the subtrees that end after node: O(1) amortized over a walk through Q1.
        /// </summary>
        public string? NextInQ1(string node) => NextInQ1(Require(node))?.Name;

        public DNode? NextInQ1(DNode node) {
            Own(node);
            var c = node.C1.Next!;
            while (c.Name == null) c = c.Next!;
            return c.Node as DNode;                                 // null for SINK
        }

        /// <summary>
        /// Last node of the subtree of node in Q1 (the subtree is the block from node to it). Goes
        /// back from the closing cell of node over the closing cells that precede it: O(length of the
        /// path of last children below node).
        /// </summary>
        public string SubtreeLast(string node) => SubtreeLast(Require(node)).Name;

        public DNode SubtreeLast(DNode node) {
            Own(node);
            var c = End1(node);
            while (c.Name == null) c = c.Prev!;
            return (DNode)c.Node!;
        }

        // -- structural reconfiguration -------------------------------------------

        /// <summary>Remove node; its children are re-attached to its parent, in its place. The root cannot be deleted.</summary>
        public void Delete(string node) => Delete(Require(node));

        public void Delete(DNode node) {
            Own(node);
            if (node.Up == _source) throw new InvalidOperationException("the root cannot be deleted");
            var parent = node.Up!;
            var siblings = parent.Kids!;
            int i = siblings.IndexOf(node);
            siblings.RemoveAt(i);
            if (node.Kids != null) {
                siblings.InsertRange(i, node.Kids);
                foreach (var c in node.Kids) c.Up = parent;
            }
            _q1.RemoveCell(node.C1);
            if (!Single) _q2!.RemoveCell(node.C2);
            Close(node);
            if (siblings.Count == 0) {
                parent.Kids = null;
                Close(parent);
            }
            Forget(node);
        }

        /// <summary>Remove node together with all its descendants; returns their names in Q1 order.</summary>
        public List<string> DeleteSubtree(string node) => DeleteSubtree(Require(node));

        public List<string> DeleteSubtree(DNode node) {
            Own(node);
            if (node.Up == _source) throw new InvalidOperationException("the root cannot be deleted");
            var cells = _q1.CutBlockCells(node.C1, End1(node));
            if (!Single) _q2!.CutBlockCells(node.C2, End2(node));
            var removed = new List<DNode>();
            foreach (var c in cells) if (c.Name != null) removed.Add((DNode)c.Node!);
            var parent = node.Up!;
            parent.Kids!.Remove(node);
            if (parent.Kids.Count == 0) {
                parent.Kids = null;
                Close(parent);
            }
            foreach (var n in removed) Forget(n);
            return removed.Select(n => n.Name).ToList();
        }

        /// <summary>
        /// Detach the subtree rooted at subtreeRoot and attach it as the last child of newParent.
        /// newParent must not lie inside the moved subtree; the root cannot be moved. Handles stay valid.
        /// </summary>
        public void CutNPaste(string subtreeRoot, string newParent) => CutNPaste(Require(subtreeRoot), Require(newParent));

        public void CutNPaste(DNode subtreeRoot, DNode newParent) {
            Own(subtreeRoot);
            Own(newParent);
            var u = subtreeRoot;
            if (u.Up == _source) throw new InvalidOperationException("the root cannot be moved");
            if (newParent == u || Reach(u, newParent))
                throw new InvalidOperationException("newParent lies inside the subtree being moved");
            var block1 = _q1.CutBlockCells(u.C1, End1(u));
            var block2 = Single ? null : _q2!.CutBlockCells(u.C2, End2(u));
            var old = u.Up!;
            old.Kids!.Remove(u);
            if (old.Kids.Count == 0) {
                old.Kids = null;
                Close(old);
            }
            // Same placement rule as Insert: Q2 directly after the parent,
            // Q1 directly before the parent's closing cell.
            Open(newParent);
            if (!Single) _q2!.PasteCellsAfter(block2!, newParent.C2);
            _q1.PasteCellsAfter(block1, newParent.E1!.Prev!);
            u.Up = newParent;
            (newParent.Kids ??= new List<DNode>()).Add(u);
            Reshapes++;
        }

        private void Forget(DNode n) {
            _nodes.Remove(n.Name);
            n.Owner = null;
            Reshapes++;
            n.Up = null;
            n.Kids = null;
            n.E1 = n.E2 = null;
        }

        // -- accessors -------------------------------------------------------------

        public string? Root => RootNode?.Name;
        public DNode? RootNode => _source.Kids is { Count: > 0 } k ? k[0] : null;
        public string Source => Marker.Source;
        public string Sink => Marker.Sink;

        /// <summary>Read-only view of the Q1 projection, for list-level checks (IsLeftOf, Index, ...).</summary>
        public Projection Q1 { get; }

        /// <summary>Read-only view of the Q2 projection, as Q1. An EulerTree has none (NotSupportedException).</summary>
        public Projection Q2 => _v2 ?? throw new NotSupportedException("an EulerTree keeps Q1 only; it has no Q2");

        public int Size => _nodes.Count;

        /// <summary>For tests: the lists themselves, closing cells included.</summary>
        internal DList List1 => _q1;
        internal DList? List2 => _q2;
        public List<string> Nodes => _q1.ToList();
        public string EdgeLog => string.Join("\n", _edgeLog);

        public override string ToString() =>
            $"{GetType().Name}('{TreeId}', size={Size})\n  {_q1}" + (Single ? "" : $"\n  {_q2}");

        /// <summary>Handle of the node with this name. Throws if absent.</summary>
        public DNode GetNode(string name) => Require(name);

        public bool TryGetNode(string name, [System.Diagnostics.CodeAnalysis.MaybeNullWhen(false)] out DNode node) => _nodes.TryGetValue(name, out node);

        // -- and/or queries on the topology -----------------------------------------

        /// <summary>Constructed node VMin: the minimum of each index over the nodes, in the target role (see the class <c>VMin</c>).</summary>
        public VMin VMin(IEnumerable<string> nodes) {
            var c = new VMin(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        public VMin VMin(IEnumerable<DNode> nodes) {
            var c = new VMin(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        /// <summary>Constructed node VMax: the maximum of each index over the nodes, in the target role (see the class <c>VMax</c>).</summary>
        public VMax VMax(IEnumerable<string> nodes) {
            var c = new VMax(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        public VMax VMax(IEnumerable<DNode> nodes) {
            var c = new VMax(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        /// <summary>Constructed node UMin: the minimum of each index over the nodes, in the source role (see the class <c>UMin</c>).</summary>
        public UMin UMin(IEnumerable<string> nodes) {
            var c = new UMin(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        public UMin UMin(IEnumerable<DNode> nodes) {
            var c = new UMin(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        /// <summary>Constructed node UMax: the maximum of each index over the nodes, in the source role (see the class <c>UMax</c>).</summary>
        public UMax UMax(IEnumerable<string> nodes) {
            var c = new UMax(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        public UMax UMax(IEnumerable<DNode> nodes) {
            var c = new UMax(this);
            foreach (var n in nodes) c.Add(n);
            return c;
        }

        // -- queries ---------------------------------------------------------------

        public bool Contains(string node) => node != null && _nodes.ContainsKey(node);

        /// <summary>Parent of node; null for the root. Throws if node is absent.</summary>
        public string? GetParent(string node) => Require(node).Parent?.Name;

        /// <summary>The children of node, in Q1 order.</summary>
        public List<string> Children(string node) {
            var n = Require(node);
            return n.Kids == null ? new List<string>() : n.Kids.Select(c => c.Name).ToList();
        }

        /// <summary>
        /// True if there is a directed path of length at least 1 from u to v (irreflexive). A name
        /// not in the tree reaches nothing and is reached by nothing; with Strict it throws instead.
        /// </summary>
        public bool CanReach(string u, string v) {
            var a = Lookup(u);
            if (a == null) return false;
            var b = Lookup(v);
            return b != null && Reach(a, b);
        }

        /// <summary>Reachability on handles: two position comparisons, no lookup. False for removed nodes (Strict: throws).</summary>
        public bool CanReach(DNode u, DNode v) => Live(u) && Live(v) && Reach(u, v);

        /// <summary>
        /// u reaches v. Two lists: u precedes v in Q1 and in Q2. One list (EulerTree): v lies strictly
        /// inside u's block in Q1, before u's closing cell. Integer positions are compared directly.
        /// </summary>
        internal bool Reach(DNode u, DNode v) {
            if (_int) {
                if (u.C1.Num >= v.C1.Num) return false;
                return Single ? v.C1.Num < End1(u).Num : u.C2.Num < v.C2.Num;
            }
            if (!DList.Less(u.C1, v.C1)) return false;
            return Single ? DList.Less(v.C1, End1(u)) : DList.Less(u.C2, v.C2);
        }

        /// <summary>
        /// x precedes y in the second coordinate: Q2, or in one list the end of the block in reverse
        /// order (y's block ends before x's), which takes the place of the Q2 position.
        /// </summary>
        internal bool Lt2(DNode x, DNode y) {
            if (Single) {
                DList.Cell a = End1(y), b = End1(x);
                return _int ? a.Num < b.Num : DList.Less(a, b);
            }
            return _int ? x.C2.Num < y.C2.Num : DList.Less(x.C2, y.C2);
        }

        /// <summary>x precedes y in Q1.</summary>
        internal bool Lt1(DNode x, DNode y) => _int ? x.C1.Num < y.C1.Num : DList.Less(x.C1, y.C1);

        public bool CanNotReach(string u, string v) => !CanReach(u, v);
        public bool CanNotReach(DNode u, DNode v) => !CanReach(u, v);

        /// <summary>True if node is the root; false for null or a name not in the tree (Strict: throws).</summary>
        public bool IsRoot(string? node) => Lookup(node) is DNode n && n.Up == _source;
        public bool IsRoot(DNode node) => Live(node) && node.Up == _source;

        public bool IsLeaf(string node) => IsLeaf(Require(node));
        public bool IsLeaf(DNode node) {
            Own(node);
            return node.Kids is not { Count: > 0 };
        }

        /// <summary>True if u is a proper ancestor of v.</summary>
        public bool IsAncestor(string u, string v) => CanReach(u, v);
        public bool IsAncestor(DNode u, DNode v) => CanReach(u, v);

        /// <summary>True if u lies below v. Equivalent to IsAncestor(v, u).</summary>
        public bool IsDescendant(string u, string v) => IsAncestor(v, u);
        public bool IsDescendant(DNode u, DNode v) => IsAncestor(v, u);

        /// <summary>True if both nodes are in this tree (and so share its root).</summary>
        public bool SameSubtree(string u, string v) => Contains(u) && Contains(v);

        /// <summary>Nodes of the subtree rooted at node, in Q1 order.</summary>
        public List<string> Subtree(string node) => SubtreeNodes(Require(node)).Select(n => n.Name).ToList();

        private static List<DNode> SubtreeNodes(DNode node) {
            var result = new List<DNode> { node };
            var end = End1(node);
            for (var c = node.C1; c != end; ) {
                c = c.Next!;
                if (c.Name != null) result.Add((DNode)c.Node!);
            }
            return result;
        }

        public int SubtreeSize(string node) => SubtreeNodes(Require(node)).Count;

        /// <summary>[node, parent, ..., root].</summary>
        public List<string> PathToRoot(string node) {
            var result = new List<string>();
            for (var n = Require(node); n != _source; n = n.Up!) result.Add(n.Name);
            return result;
        }

        /// <summary>[root, ..., parent, node].</summary>
        public List<string> RootToPath(string node) {
            var path = PathToRoot(node);
            path.Reverse();
            return path;
        }

        /// <summary>Nodes from u down to v, both included; [u] when u == v.</summary>
        public List<string> Path(string u, string v) {
            var a = Require(u);
            var b = Require(v);
            if (a != b && !Reach(a, b)) throw new InvalidOperationException($"'{u}' cannot reach '{v}'");
            var result = new List<string>();
            for (var n = b; ; n = n.Up!) {
                result.Add(n.Name);
                if (n == a) break;
            }
            result.Reverse();
            return result;
        }

        /// <summary>Distance from the root; the root has depth 0.</summary>
        public int Depth(string node) => Depth(Require(node));

        public int Depth(DNode node) {
            Own(node);
            int d = 0;
            for (var n = node.Up!; n != _source; n = n.Up!) d++;
            return d;
        }

        private DNode Require(string node) {
            ArgumentNullException.ThrowIfNull(node);
            return _nodes.TryGetValue(node, out var n) ? n : throw new KeyNotFoundException($"node '{node}' is not in the tree");
        }

        /// <summary>The node of this name for a query: null if absent (Strict: KeyNotFoundException).</summary>
        internal DNode? Lookup(string? node) {
            if (node != null && _nodes.TryGetValue(node, out var n)) return n;
            if (Strict) throw new KeyNotFoundException($"node '{node ?? "null"}' is not in the tree");
            return null;
        }

        /// <summary>True if the handle belongs to this tree; false otherwise (Strict: ArgumentException).</summary>
        internal bool Live(DNode node) {
            if (node.Owner == this) return true;
            if (Strict) throw new ArgumentException($"node '{node.Name}' does not belong to this tree");
            return false;
        }

        internal void Own(DNode node) {
            if (node.Owner != this) throw new ArgumentException($"node '{node.Name}' does not belong to this tree");
        }
    }
}
