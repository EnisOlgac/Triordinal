namespace Triordinal.DTree.Euler {

    /// <summary>
    /// Single-rooted directed tree encoded by one list: DTree's Q1 with its closing cells, the
    /// classical parenthesis (Euler-tour) encoding.
    /// </summary>
    /// <remarks>
    /// Every node with children has a closing cell directly after the last cell of its subtree, so the
    /// subtree of u is the block from u to its closing cell (u alone for a leaf). Node u reaches node v
    /// exactly when v's cell lies strictly inside u's block: two position comparisons, as in DTree.
    /// The API is DTree's (names or handles, Insert / InsertAfter / InsertBefore, Delete, DeleteSubtree,
    /// CutNPaste, strict mode, the constructed nodes VMin, VMax, UMin, UMax); in one list a constructed
    /// node uses the end of each member's block in place of its Q2 position. Q2 does not exist
    /// (NotSupportedException). For trees, the Euler tour holds the same information as DTree's two
    /// lists and is faster to maintain; see docs/prior-art.md. Ported from the Python reference
    /// triordinal.dtree.euler.
    /// </remarks>
    public sealed class EulerTree : global::DirectedTrees.DTree {
        public EulerTree(string treeId = "E1", bool strict = false, Positions positions = Positions.Rational)
            : base(treeId, strict, positions, true) { }

        /// <summary>Read a description file as DTree.FromFile does, into an EulerTree.</summary>
        public static new EulerTree FromFile(string path, string? treeId = null, bool strict = false, Positions positions = Positions.Rational) {
            var tree = new EulerTree(treeId ?? System.IO.Path.GetFileNameWithoutExtension(path), strict, positions);
            tree.ReadFile(path);
            return tree;
        }
    }
}
