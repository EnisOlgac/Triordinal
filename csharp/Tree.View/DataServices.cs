using System;
using System.Collections.Generic;
using System.IO;
using System.Windows;

using Microsoft.Win32;

namespace Tree.View {
    public partial class MainWindow : Window {

        public string TreeFile { get; set; }
        public string TreeDir { get; set; }
        public string TreeName { get; set; }
        public string TreeExt { get; set; }
        public string LogDir { get; set; }
        public string LogFile { get; set; }
        internal string DGMLTreeFile;
        internal string DGMLDir;
        internal string DGMLTreeName;

        public bool OpenDiTree() {
            bool openOK;
            OpenFileDialog openFile = new OpenFileDialog() { Filter = "csx files (*.csx)|*.csx|All files (*.*)|*.*" };
            if (openOK = openFile.ShowDialog() == true) {
                TreeFile = openFile.FileName;
                TreeDir = Path.GetDirectoryName(TreeFile);
                TreeName = Path.GetFileNameWithoutExtension(TreeFile);
                TreeExt = Path.GetExtension(TreeFile);
                LogDir = Directory.CreateDirectory(TreeDir + "\\Log\\").FullName;
                LogFile = LogDir + TreeName + ".log";
            }
            return (openOK);
        }

        public void ReadDiGraph() {
            var graph = new StreamReader(TreeFile);
            string line;
            int numLines = 0;
            while ((line = graph.ReadLine()) != null) {
                numLines++;
                if (line == "") continue;
                if (line.Substring(0, 1) == "#") { continue; }
                if (line.Substring(0, 2) == "--") { continue; }
                if (line.Substring(0, 2) == "**") { continue; }
                if (line.Substring(0, 2) == "@@") { break; }
                if (line.IndexOfAny(new[] { ':', '>', '<' }) < 0) continue;
                try {
                    T.AddLine(line);                                // "p: c1; c2", "s > c1; c2" or "s < c1; c2"
                } catch (Exception e) when (e is ArgumentException || e is KeyNotFoundException || e is InvalidOperationException) {
                    MessageBox.Show($"Line {numLines}: \"{line.Trim()}\" not fully applied.\n{e.Message}", "DTree", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }
            graph.Close();
        }
    }
}