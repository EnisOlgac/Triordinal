using System.Windows;
using DirectedTrees;

namespace Tree.View {
    public partial class MainWindow : Window {
        public MainWindow() { InitializeComponent(); }

        DTree T;

        private void SelectDiGraph() {
            var openOK = OpenDiTree();
            if (openOK) {
                Title = "Topology and Structure of a Directed Tree - " + TreeFile;
                T = new DTree(TreeName);
                TDef.Text = "";
                ReadDiGraph();
                TDef.Text = T.EdgeLog;
                ShowDTree();
            }
        }
        private void Select_DiTree(object sender, RoutedEventArgs e) { SelectDiGraph(); }
    }
}
