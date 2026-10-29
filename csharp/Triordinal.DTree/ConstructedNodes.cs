using Triordinal;

namespace DirectedTrees {

    /// <summary>
    /// A constructed node for a set S of tree nodes (E. Olgac, "Topology and Structure of Directed
    /// Graphs - Inducing a Subgraph", 2021): the minimum (VMin, UMin) or maximum (VMax, UMax) of
    /// each index over S. V means S takes the target role, CanReach(u, S), and U the source role,
    /// CanReach(S, v); UMin and VMin hold the same numbers, as do UMax and VMax.
    /// </summary>
    /// <remarks>
    /// It stores no positions, only the members (kept in Q1 order) and, for each of Q1 and Q2, the
    /// member holding the minimal (or maximal) index there; the two may be different nodes, so the
    /// constructed node usually corresponds to no real node. Insertions and renumbering keep the
    /// order of existing nodes, so it stays valid while the tree grows. After a deletion or a
    /// CutNPaste it is recomputed from the remaining members on its next use. Members are added
    /// with Add and removed with Discard.
    /// </remarks>
    public abstract class ConstructedNode {
        private protected readonly DTree Tree;
        private protected readonly List<DNode> Members = new();    // in Q1 order
        private readonly HashSet<DNode> _seen = new();
        private protected DNode? Q1Node;                            // member with the extreme Q1 index
        private protected DNode? Q2Node;                            // member with the extreme Q2 index
        private readonly bool _lowest;
        private int _reshapes;

        private protected ConstructedNode(DTree tree, bool lowest) {
            Tree = tree;
            _lowest = lowest;
            _reshapes = tree.Reshapes;
        }

        private bool Better(DList.Cell candidate, DList.Cell current) =>
            _lowest ? DList.Less(candidate, current) : DList.Less(current, candidate);

        /// <summary>Add a node of the tree to the set; returns the constructed node itself.</summary>
        public ConstructedNode Add(string node) => Add(Tree.GetNode(node));

        public ConstructedNode Add(DNode node) {
            Tree.Own(node);
            Check();
            if (!_seen.Add(node)) return this;
            int lo = 0, hi = Members.Count;                         // keep members in Q1 order
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(node.C1, Members[mid].C1)) hi = mid; else lo = mid + 1;
            }
            Members.Insert(lo, node);
            if (Q1Node == null || Better(node.C1, Q1Node.C1)) Q1Node = node;
            if (Q2Node == null || Better(node.C2, Q2Node.C2)) Q2Node = node;
            Added(node);
            return this;
        }

        /// <summary>
        /// Remove a node from the set; no error if it is not a member. Returns the constructed node
        /// itself. If the node held an index (the minimal or maximal position in Q1 or Q2), the index
        /// nodes are recomputed in O(k). Typical use: expanding a node in a tree view.
        /// </summary>
        public ConstructedNode Discard(string node) =>
            Tree.TryGetNode(node, out var n) ? Discard(n) : this;

        public ConstructedNode Discard(DNode node) {
            Check();
            if (!_seen.Remove(node)) return this;
            int lo = 0, hi = Members.Count;                         // members are in Q1 order
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(Members[mid].C1, node.C1)) lo = mid + 1; else hi = mid;
            }
            Members.RemoveAt(lo);
            if (node == Q1Node || node == Q2Node) {
                Q1Node = Q2Node = null;
                foreach (var n in Members) {
                    if (Q1Node == null || Better(n.C1, Q1Node.C1)) Q1Node = n;
                    if (Q2Node == null || Better(n.C2, Q2Node.C2)) Q2Node = n;
                }
            }
            Discarded(node);
            return this;
        }

        /// <summary>True if the node is a member of the set.</summary>
        public bool Contains(string node) => Tree.TryGetNode(node, out var n) && Contains(n);

        public bool Contains(DNode node) { Check(); return _seen.Contains(node); }

        /// <summary>Hook for subclasses that keep more than the index nodes.</summary>
        private protected virtual void Discarded(DNode node) { }

        /// <summary>Hook for subclasses that keep more than the index nodes.</summary>
        private protected virtual void Added(DNode node) { }

        /// <summary>Hook for subclasses that keep more than the index nodes.</summary>
        private protected virtual void Rebuilt() { }

        /// <summary>Drop deleted members and recompute the index nodes.</summary>
        public void Refresh() {
            Members.RemoveAll(n => n.Owner != Tree);
            Members.Sort((a, b) => a == b ? 0 : DList.Less(a.C1, b.C1) ? -1 : 1);
            _seen.Clear();
            Q1Node = Q2Node = null;
            foreach (var n in Members) {
                _seen.Add(n);
                if (Q1Node == null || Better(n.C1, Q1Node.C1)) Q1Node = n;
                if (Q2Node == null || Better(n.C2, Q2Node.C2)) Q2Node = n;
            }
            _reshapes = Tree.Reshapes;
            Rebuilt();
        }

        private protected void Check() {
            if (_reshapes != Tree.Reshapes) Refresh();
        }

        /// <summary>The members, in Q1 order.</summary>
        public List<string> MemberNames {
            get { Check(); return Members.Select(n => n.Name).ToList(); }
        }

        /// <summary>The members holding the minimal (VMin, UMin) or maximal (VMax, UMax) index in Q1 and in Q2 (possibly two different nodes).</summary>
        public (string? Q1, string? Q2) IndexNodes {
            get { Check(); return (Q1Node?.Name, Q2Node?.Name); }
        }

        public int Count {
            get { Check(); return Members.Count; }
        }

        /// <summary>u lies strictly left of the constructed node in both Q1 and Q2.</summary>
        private protected bool Below(DNode u) => DList.Less(u.C1, Q1Node!.C1) && DList.Less(u.C2, Q2Node!.C2);

        /// <summary>v lies strictly right of the constructed node in both Q1 and Q2.</summary>
        private protected bool Above(DNode v) => DList.Less(Q1Node!.C1, v.C1) && DList.Less(Q2Node!.C2, v.C2);
    }

    /// <summary>
    /// S in the target role, CanReach(u, S). Minimum of each index over a node set: u reaches all
    /// of the set exactly when u lies strictly left of VMin in both Q1 and Q2.
    /// </summary>
    public sealed class VMin : ConstructedNode {
        public VMin(DTree tree) : base(tree, true) { }

        /// <summary>True if u reaches every node of the set (vacuously true for an empty set).</summary>
        public bool ReachesAll(string u) => Tree.TryGetNode(u, out var n) && ReachesAll(n);

        public bool ReachesAll(DNode u) {
            Check();
            if (u.Owner != Tree) return false;
            return Q1Node == null || Below(u);
        }
    }

    /// <summary>
    /// S in the target role, CanReach(u, S). Maximum of each index over a node set: lying strictly
    /// left of VMax in both Q1 and Q2 is necessary for u to reach some of the set, but not
    /// sufficient; the exact answer uses the members in Q1 order.
    /// </summary>
    public sealed class VMax : ConstructedNode {
        public VMax(DTree tree) : base(tree, false) { }

        /// <summary>Fast rejection: false means u reaches no node of the set; true is not a confirmation.</summary>
        public bool MayReachSome(string u) => Tree.TryGetNode(u, out var n) && MayReachSome(n);

        public bool MayReachSome(DNode u) {
            Check();
            return Q1Node != null && u.Owner == Tree && Below(u);
        }

        /// <summary>
        /// True if u reaches at least one node of the set (exact, O(log k)). The subtree of u is the
        /// block directly after u in Q1, so u reaches some member exactly when the first member after
        /// u in Q1 lies in it: a binary search over the members and one reachability test.
        /// </summary>
        public bool ReachesSome(string u) => Tree.TryGetNode(u, out var n) && ReachesSome(n);

        public bool ReachesSome(DNode u) {
            if (!MayReachSome(u)) return false;
            int lo = 0, hi = Members.Count;
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(u.C1, Members[mid].C1)) hi = mid; else lo = mid + 1;
            }
            return lo < Members.Count && DTree.Reaches(u, Members[lo]);
        }
    }

    /// <summary>
    /// S in the source role, CanReach(S, v). Maximum of each index over a node set: v is reached by
    /// all of the set exactly when v lies strictly right of UMax in both Q1 and Q2.
    /// </summary>
    public sealed class UMax : ConstructedNode {
        public UMax(DTree tree) : base(tree, false) { }

        /// <summary>True if every node of the set reaches v (vacuously true for an empty set).</summary>
        public bool ReachedByAll(string v) => Tree.TryGetNode(v, out var n) && ReachedByAll(n);

        public bool ReachedByAll(DNode v) {
            Check();
            if (v.Owner != Tree) return false;
            return Q1Node == null || Above(v);
        }
    }

    /// <summary>
    /// S in the source role, CanReach(S, v). Minimum of each index over a node set: lying strictly
    /// right of UMin in both Q1 and Q2 is necessary for v to be reached by some of the set, but not
    /// sufficient; the exact answer uses the topmost members.
    /// </summary>
    /// <remarks>
    /// The topmost members (those with no ancestor in the set) are kept in Q1 order. Their subtrees
    /// are disjoint, so if one of them is an ancestor of v, no other topmost member lies between it
    /// and v in Q1: the last topmost member before v in Q1 is the only one to test.
    /// </remarks>
    public sealed class UMin : ConstructedNode {
        private readonly List<DNode> _tops = new();                 // topmost members, in Q1 order

        public UMin(DTree tree) : base(tree, true) { }

        /// <summary>Number of topmost members strictly left of v in Q1.</summary>
        private int TopsBefore(DNode v) {
            int lo = 0, hi = _tops.Count;
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (DList.Less(_tops[mid].C1, v.C1)) lo = mid + 1; else hi = mid;
            }
            return lo;
        }

        private bool Covered(DNode v) {
            int i = TopsBefore(v);
            return i > 0 && DTree.Reaches(_tops[i - 1], v);
        }

        private protected override void Added(DNode node) {
            if (Covered(node)) return;                              // an ancestor of node is already in the set
            int i = TopsBefore(node);
            while (i < _tops.Count && DTree.Reaches(node, _tops[i]))
                _tops.RemoveAt(i);                                  // node is above them: no longer topmost
            _tops.Insert(i, node);
        }

        private protected override void Discarded(DNode node) {
            if (_tops.Contains(node)) Rebuilt();                    // members it covered may become topmost
        }

        private protected override void Rebuilt() {
            _tops.Clear();
            foreach (var v in Members)                              // Q1 order: ancestors come first
                if (_tops.Count == 0 || !DTree.Reaches(_tops[^1], v)) _tops.Add(v);
        }

        /// <summary>Fast rejection: false means no node of the set reaches v; true is not a confirmation.</summary>
        public bool MayBeReachedBySome(string v) => Tree.TryGetNode(v, out var n) && MayBeReachedBySome(n);

        public bool MayBeReachedBySome(DNode v) {
            Check();
            return Q1Node != null && v.Owner == Tree && Above(v);
        }

        /// <summary>True if at least one node of the set reaches v (exact, O(log k)).</summary>
        public bool ReachedBySome(string v) => Tree.TryGetNode(v, out var n) && ReachedBySome(n);

        public bool ReachedBySome(DNode v) => MayBeReachedBySome(v) && Covered(v);

        /// <summary>
        /// The topmost member of the set that reaches v, or null if no member does (O(log k)).
        /// With the collapsed nodes of a tree view as a UMin, this is the visible row that contains
        /// v: null means v itself is visible.
        /// </summary>
        public string? Covering(string v) => Tree.TryGetNode(v, out var n) ? Covering(n)?.Name : null;

        public DNode? Covering(DNode v) {
            Check();
            if (v.Owner != Tree) return null;
            int i = TopsBefore(v);
            return i > 0 && DTree.Reaches(_tops[i - 1], v) ? _tops[i - 1] : null;
        }
    }
}
