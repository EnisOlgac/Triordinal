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
        internal List<DNode>? Kids;             // children in insertion order (Q1 order)
        internal DList.Cell C1 = null!;         // position in Q1
        internal DList.Cell C2 = null!;         // position in Q2
        internal DNode? Last;                   // hint: last node of the subtree in Q1 (validated before use)

        /// <summary>The parent node; null for the root.</summary>
        public DNode? Parent => Up == null || Up.Owner == null ? null : Up;

        /// <summary>The children in insertion order (a copy).</summary>
        public IReadOnlyList<DNode> Children => Kids == null ? Array.Empty<DNode>() : Kids.ToArray();

        /// <summary>False once the node has been deleted from its tree.</summary>
        public bool IsInTree => Owner != null;

        public override string ToString() => Name;
    }

    /// <summary>
    /// Single-rooted directed tree encoded by two linear projections Q1 and Q2.
    /// </summary>
    /// <remarks>
    /// Q1 is the pre-order with children left to right (insertion order); Q2 the pre-order
    /// with siblings right to left. Node u reaches node v if and only if u strictly precedes v
    /// in both Q1 and Q2 (irreflexive: no node reaches itself). A new child is the last child of
    /// its parent in Q1 and the first in Q2, so every change is local to both lists.
    /// Every method is available with node names and, for speed, with <see cref="DNode"/>
    /// handles, which refer to their positions directly (the idea of using addresses as ids is
    /// Enis Olgac's, from his original implementation).
    /// Design and API: Enis Olgac. This C# version mirrors the Python reference implementation,
    /// which was written with Claude (Anthropic).
    /// </remarks>
    public sealed class DTree {
        private readonly Dictionary<string, DNode> _nodes = new();
        private readonly DNode _source;         // sentinel: parent of the root
        private readonly DList _q1;
        private readonly DList _q2;
        private readonly List<string> _edgeLog = new();
        internal int Reshapes;                  // counts deletions and moves; insertions keep the order of existing nodes

        public DTree(string treeId = "P1") {
            TreeId = treeId;
            _q1 = new DList(treeId + ".Q1");
            _q2 = new DList(treeId + ".Q2");
            _source = new DNode(Marker.Source, null) { C1 = _q1.FirstCell, C2 = _q2.FirstCell };
        }

        public string TreeId { get; }

        // -- construction -----------------------------------------------------------

        /// <summary>
        /// Read the format used by the .csx examples: "parent: child1; child2" adds last children,
        /// "sibling > child1; child2" inserts siblings directly after sibling (in that order),
        /// "sibling &lt; child1; child2" directly before it.
        /// </summary>
        public static DTree FromFile(string path, string? treeId = null) {
            var tree = new DTree(treeId ?? System.IO.Path.GetFileNameWithoutExtension(path));
            foreach (var raw in File.ReadLines(path)) {
                var line = raw.Trim().TrimStart('\uFEFF');
                if (line.Length == 0 || line.StartsWith('#') || line.StartsWith("--") || line.StartsWith("**")) continue;
                if (line.StartsWith("@@")) break;
                if (line.IndexOfAny(new[] { ':', '>', '<' }) < 0) continue;
                tree.AddLine(line);
            }
            return tree;
        }

        /// <summary>Apply one line of the description format (see FromFile); returns the new handles.</summary>
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

        /// <summary>
        /// Add the edge parent -> child and return the child's handle. The first call makes parent
        /// the root; afterwards parent must already exist and child must not.
        /// </summary>
        public DNode Insert(string parent, string child) {
            if (IsMarker(parent) || IsMarker(child))
                throw new ArgumentException("SOURCE/SINK markers cannot be tree nodes");
            if (_nodes.Count == 0) {
                if (parent == child) throw new ArgumentException($"child '{child}' is already in the tree");
                Attach(_source, NewNode(parent));
            }
            if (!_nodes.TryGetValue(parent, out var p))
                throw new KeyNotFoundException($"parent '{parent}' is not in the tree");
            return InsertUnder(p, child);
        }

        /// <summary>Add a child under an existing node handle and return the child's handle.</summary>
        public DNode Insert(DNode parent, string child) {
            Own(parent);
            if (IsMarker(child)) throw new ArgumentException("SOURCE/SINK markers cannot be tree nodes");
            return InsertUnder(parent, child);
        }

        private DNode InsertUnder(DNode parent, string child) {
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            var c = NewNode(child);
            Attach(parent, c);
            _edgeLog.Add($"({parent.Name}, {child})");
            return c;
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
            var w = LastInQ1(s);
            var n = Link(child, p, i + 1, w.C1, s.C2.Prev!);
            if (i + 1 == p.Kids.Count - 1) p.Last = n;              // n is now the last node of p's subtree
            _edgeLog.Add($"({s.Name} > {child})");
            return n;
        }

        /// <summary>
        /// Insert child as a sibling directly before sibling (same parent) and return its handle. In Q1
        /// it goes directly before the sibling, in Q2 after the end of the sibling's subtree there
        /// (directly before the previous sibling; for a first child, after the end of the parent's
        /// subtree in Q2, found by following first children); no other node moves.
        /// </summary>
        public DNode InsertBefore(string sibling, string child) => InsertBefore(Require(sibling), child);

        public DNode InsertBefore(DNode sibling, string child) {
            var s = CheckSibling(sibling, child);
            var p = s.Up!;
            int i = p.Kids!.IndexOf(s);
            var q2After = i > 0 ? p.Kids[i - 1].C2.Prev! : LastInQ2(s).C2;
            var n = Link(child, p, i, s.C1.Prev!, q2After);
            _edgeLog.Add($"({s.Name} < {child})");
            return n;
        }

        private DNode CheckSibling(DNode sibling, string child) {
            Own(sibling);
            if (IsMarker(child)) throw new ArgumentException("SOURCE/SINK markers cannot be tree nodes");
            if (sibling.Up == _source) throw new InvalidOperationException("the root has no siblings");
            if (_nodes.ContainsKey(child)) throw new ArgumentException($"child '{child}' is already in the tree");
            return sibling;
        }

        /// <summary>Create a child of p at position index among p's children, linked after the given cells.</summary>
        private DNode Link(string name, DNode p, int index, DList.Cell q1After, DList.Cell q2After) {
            var n = NewNode(name);
            n.C2 = _q2.InsertNewAfter(name, q2After);
            n.C1 = _q1.InsertNewAfter(name, q1After);
            n.C1.Node = n.C2.Node = n;
            n.Up = p;
            p.Kids!.Insert(index, n);
            return n;
        }

        private static bool IsMarker(string v) => v == Marker.Source || v == Marker.Sink;

        private DNode NewNode(string name) {
            var n = new DNode(name, this);
            _nodes[name] = n;
            return n;
        }

        private void Attach(DNode parent, DNode child) {
            var last = LastInQ1(parent);
            child.C2 = _q2.InsertNewAfter(child.Name, parent.C2);   // first child in Q2
            child.C1 = _q1.InsertNewAfter(child.Name, last.C1);     // last child in Q1
            child.C1.Node = child.C2.Node = child;
            child.Up = parent;
            (parent.Kids ??= new List<DNode>()).Add(child);
            parent.Last = child;                                    // child is now the last node of parent's subtree
        }

        // -- the end of a subtree --------------------------------------------------

        internal static int Budget = 8;  // steps of the plain walk before the validated hint is used (tests may set 0)

        /// <summary>x is p or lies in p's subtree.</summary>
        private static bool InSubtree(DNode p, DNode x) =>
            x == p || (DList.Less(p.C1, x.C1) && DList.Less(p.C2, x.C2));

        /// <summary>x is the last node of p's subtree in Q1: x lies in it and x's Q1 successor does not.</summary>
        private bool IsLast(DNode p, DNode? x) {
            if (x == null || x.Owner != this || !InSubtree(p, x)) return false;
            var next = x.C1.Next!;
            return next.Den == 0 || !InSubtree(p, (DNode)next.Node!);
        }

        /// <summary>
        /// Last node of p's subtree in Q1. A short walk down the last children finds it on ordinary
        /// trees; beyond the budget, the end remembered last time (p.Last) is used if it validates in
        /// O(1); otherwise the walk continues, stops at a node whose own hint validates, and every node
        /// passed gets the found end as its new hint (path compression). Stale hints are never used,
        /// so ancestors' hints need no update when a subtree grows.
        /// </summary>
        private DNode LastInQ1(DNode p) {
            var w = p;
            for (int k = 0; k < Budget && w.Kids is { Count: > 0 } kids; k++) w = kids[^1];
            if (w.Kids is not { Count: > 0 }) return w;
            if (IsLast(p, p.Last)) return p.Last!;
            var path = new List<DNode> { p };
            w = p;
            while (w.Kids is { Count: > 0 } kids) {
                w = kids[^1];
                if (IsLast(w, w.Last)) { w = w.Last!; break; }
                path.Add(w);
            }
            foreach (var v in path) v.Last = w;
            return w;
        }

        /// <summary>Last node of u's subtree in Q2 (siblings reversed): follow first children.</summary>
        private static DNode LastInQ2(DNode u) {
            var w = u;
            while (w.Kids is { Count: > 0 } kids) w = kids[0];
            return w;
        }

        /// <summary>
        /// The node after node in Q1, or null after the last node. Q1 is the display order of a tree
        /// view (parents before children, siblings in insertion order).
        /// </summary>
        public string? NextInQ1(string node) => NextInQ1(Require(node))?.Name;

        public DNode? NextInQ1(DNode node) {
            Own(node);
            return node.C1.Next?.Node as DNode;
        }

        /// <summary>Last node of the subtree of node in Q1 (the subtree is the block from node to it). Usually O(1) when asked again.</summary>
        public string SubtreeLast(string node) => LastInQ1(Require(node)).Name;

        public DNode SubtreeLast(DNode node) {
            Own(node);
            return LastInQ1(node);
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
            _q2.RemoveCell(node.C2);
            Forget(node);
        }

        /// <summary>Remove node together with all its descendants; returns their names in Q1 order.</summary>
        public List<string> DeleteSubtree(string node) => DeleteSubtree(Require(node));

        public List<string> DeleteSubtree(DNode node) {
            Own(node);
            if (node.Up == _source) throw new InvalidOperationException("the root cannot be deleted");
            var removed = SubtreeNodes(node);
            _q1.CutBlockCells(node.C1, LastInQ1(node).C1);
            _q2.CutBlockCells(node.C2, LastInQ2(node).C2);
            node.Up!.Kids!.Remove(node);
            foreach (var n in removed) Forget(n);
            return removed.Select(n => n.Name).ToList();
        }

        /// <summary>
        /// Detach the subtree rooted at subtreeRoot and attach it as the last child of newParent.
        /// newParent must not lie inside the moved subtree; the root cannot be moved.
        /// </summary>
        public void CutNPaste(string subtreeRoot, string newParent) => CutNPaste(Require(subtreeRoot), Require(newParent));

        public void CutNPaste(DNode subtreeRoot, DNode newParent) {
            Own(subtreeRoot);
            Own(newParent);
            var u = subtreeRoot;
            if (u.Up == _source) throw new InvalidOperationException("the root cannot be moved");
            if (newParent == u || CanReach(u, newParent))
                throw new InvalidOperationException("newParent lies inside the subtree being moved");
            var uLast = LastInQ1(u);
            var block1 = _q1.CutBlockCells(u.C1, uLast.C1);
            var block2 = _q2.CutBlockCells(u.C2, LastInQ2(u).C2);
            foreach (var c in block1) ((DNode)c.Node!).Owner = null;     // detached for a moment: hints into the block are not valid
            u.Up!.Kids!.Remove(u);
            // Same placement rule as Insert: Q2 right after the parent,
            // Q1 right after the current last node of the parent's subtree.
            var last = LastInQ1(newParent);
            _q2.PasteCellsAfter(block2, newParent.C2);
            _q1.PasteCellsAfter(block1, last.C1);
            foreach (var c in block1) ((DNode)c.Node!).Owner = this;
            u.Up = newParent;
            (newParent.Kids ??= new List<DNode>()).Add(u);
            newParent.Last = uLast;
            Reshapes++;
        }

        private void Forget(DNode n) {
            _nodes.Remove(n.Name);
            n.Owner = null;
            Reshapes++;
            n.Up = null;
            n.Kids = null;
            n.Last = null;
        }

        // -- accessors -------------------------------------------------------------

        public string? Root => RootNode?.Name;
        public DNode? RootNode => _source.Kids is { Count: > 0 } k ? k[0] : null;
        public string Source => Marker.Source;
        public string Sink => Marker.Sink;

        /// <summary>The Q1 projection itself, for list-level checks. Read it; change the tree only through DTree.</summary>
        public DList Q1 => _q1;

        /// <summary>The Q2 projection itself, for list-level checks. Read it; change the tree only through DTree.</summary>
        public DList Q2 => _q2;

        public int Size => _nodes.Count;
        public List<string> Nodes => _q1.ToList();
        public string EdgeLog => string.Join("\n", _edgeLog);

        public override string ToString() => $"DTree('{TreeId}', size={Size})\n  {_q1}\n  {_q2}";

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

        public bool Contains(string node) => _nodes.ContainsKey(node);

        /// <summary>Parent of node; null for the root. Throws if node is absent.</summary>
        public string? GetParent(string node) => Require(node).Parent?.Name;

        public List<string> Children(string node) {
            var n = Require(node);
            return n.Kids == null ? new List<string>() : n.Kids.Select(c => c.Name).ToList();
        }

        /// <summary>True if there is a directed path of length at least 1 from u to v (irreflexive).</summary>
        public bool CanReach(string u, string v) =>
            _nodes.TryGetValue(u, out var a) && _nodes.TryGetValue(v, out var b) && Reaches(a, b);

        /// <summary>Reachability on handles: two position comparisons, no lookup. False for removed nodes.</summary>
        public bool CanReach(DNode u, DNode v) => u.Owner == this && v.Owner == this && Reaches(u, v);

        internal static bool Reaches(DNode u, DNode v) => DList.Less(u.C1, v.C1) && DList.Less(u.C2, v.C2);

        public bool CanNotReach(string u, string v) => !CanReach(u, v);
        public bool CanNotReach(DNode u, DNode v) => !CanReach(u, v);

        public bool IsRoot(string node) => node == Root;
        public bool IsRoot(DNode node) => node.Owner == this && node.Up == _source;

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

        private List<DNode> SubtreeNodes(DNode node) {
            var result = new List<DNode>();
            var end = LastInQ1(node).C1;
            for (var c = node.C1; ; c = c.Next!) {
                result.Add(_nodes[c.Name]);
                if (c == end) break;
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
            if (a != b && !Reaches(a, b)) throw new InvalidOperationException($"'{u}' cannot reach '{v}'");
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

        private DNode Require(string node) =>
            _nodes.TryGetValue(node, out var n) ? n : throw new KeyNotFoundException($"node '{node}' is not in the tree");

        internal void Own(DNode node) {
            if (node.Owner != this) throw new ArgumentException($"node '{node.Name}' does not belong to this tree");
        }
    }
}
