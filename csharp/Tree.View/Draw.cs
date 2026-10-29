using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;

using DirectedTrees;
using Triordinal;

using static System.Math;
using static System.Windows.Controls.Canvas;

namespace Tree.View {
    public partial class MainWindow : Window {
        internal struct Figure {
            internal string V;
            internal int ColInd;
            internal int RowInd;
            internal int Left;
            internal int Top;
        }

        internal Dictionary<string, Figure> dict = new();

        internal void ShowDTree() {
            InitShow();
            Board.Children.Clear();
            var (maxRow, maxCol) = DrawSpanTreesFwd(0);
        }

        internal void InitShow() {
            CellWidth = 80;
            CellHeight = 30;
            FigWidth = 70;
            FigHeight = 20;
            MargeWidth = CellWidth - FigWidth;
        }

        internal (int, int) DrawSpanTreesFwd(int maxRow) {
            int maxCol = 0;
            string q1 = T.Q1.ToString(), q2 = T.Q2.ToString();
            (maxRow, maxCol) = DrawSpanTreeFwd(T.Q1.ToList(withMarkers: true), maxRow);
            Board.Children.Add(List(q1, CellWidth, (maxRow += 2) * CellHeight));
            Board.Children.Add(List(q2, CellWidth, (maxRow += 1) * CellHeight));
            (maxRow, maxCol) = DrawSpanTreeFwd(T.Q2.ToList(withMarkers: true), maxRow += 1);
            return (maxRow, maxCol);
        }

        internal int CellWidth;
        internal int CellHeight;
        internal int FigWidth;
        internal int FigHeight;
        internal int MargeWidth;
        internal SolidColorBrush[] Colors = { Brushes.Red, Brushes.Gold, Brushes.Blue, Brushes.Green, Brushes.Black };

        internal (int, int) DrawSpanTreeFwd(List<string> oo, int firstRow) {
            dict.Clear();
            int maxRow = 0;
            int lastCol = 0;
            int row = 0;
            int col = 1;
            Figure curr, org = new() { V = T.Source, ColInd = 1, RowInd = firstRow, Left = CellWidth + MargeWidth, Top = firstRow * CellHeight }, last = org;
            ;
            string a, u, source = T.Source, sink = T.Sink;
            int i = 1;
            string w = oo[i];
            for (; w != sink; w = oo[++i]) {
                    curr = new Figure() { V = w };
                    if (last.V != (a = T.GetParent(curr.V) ?? T.Source)) {
                        ++col;
                        if (a == source) { last = org; } else { last = dict[a]; }
                    }
                    row = last.RowInd;
                    curr.ColInd = col;
                    curr.Left = col * (CellWidth + MargeWidth);
                    curr.RowInd = ++row; ;
                    curr.Top = row * CellHeight;
                    dict.Add(curr.V, curr);
                    DrawStructure(last, curr, w);
                    maxRow = Max(maxRow, row);
                    lastCol = curr.ColInd;
                    last = curr;
                }
            return (maxRow, lastCol);
        }

        internal void DrawStructure(Figure last, Figure curr, string v) {
            Board.Children.Add(DrawSeq(last.V, curr, v));
            if (last.ColInd == curr.ColInd) {
                Board.Children.Add(ConnDown(last, curr));
            } else { Board.Children.Add(ConnRightDown(last, curr)); }
        }
        internal Line ConnDown(Figure u, Figure v) {
            var uBottom = u.Top + FigHeight;
            var conn = new Line() {
                X1 = FigWidth / 2,
                Y1 = 0,
                X2 = FigWidth / 2,
                Y2 = v.Top - uBottom,
                Stroke = Brushes.Black,
                StrokeThickness = 1
            };
            SetLeft(conn, u.Left);
            SetTop(conn, uBottom);
            return (conn);
        }
        internal Polyline ConnRightDown(Figure u, Figure v) {
            var uRight = u.Left + FigWidth;
            var midFig = FigHeight / 2;
            var points = new PointCollection() {
                new Point(0, midFig),
                new Point((v.Left - uRight) + midFig, midFig),
                new Point((v.Left - uRight) + midFig, (v.Top - u.Top))
            };
            var conn = new Polyline() {
                Points = points,
                Stroke = Brushes.Black,
                StrokeThickness = 1
            };
            SetLeft(conn, uRight);
            SetTop(conn, u.Top);
            return (conn);
        }
        internal Rectangle DrawSeq(string last, Figure f, string v) {
            Brush color;
            var t = v.Substring(0, 1);
            switch (t) {
                case "W": color = Brushes.Red; break;
                case "B": color = Brushes.Black; break;
                case "O": color = Brushes.Orange; break;
                default: color = Brushes.Gray; break;
            }
            Rectangle seq = new Rectangle() { Width = FigWidth, Height = FigHeight, StrokeThickness = 2, Stroke = color };
            SetTop(seq, f.Top);
            SetLeft(seq, f.Left);
            Board.Children.Add(Label(f));
            return (seq);
        }
        internal TextBox Label(Figure f) {
            TextBox label = new TextBox() {
                Width = FigWidth,
                Height = FigHeight,
                BorderThickness = new Thickness(0),
                HorizontalContentAlignment = HorizontalAlignment.Center,
                VerticalContentAlignment = VerticalAlignment.Center,
                FontFamily = new FontFamily("Comic Sans MS"),
                FontSize = 14,
                Text = f.V
            };
            SetLeft(label, f.Left);
            SetTop(label, f.Top);
            return (label);
        }
        internal TextBox List(string text, int left, int top) {
            TextBox label = new TextBox() {
                Width = text.Length * 8,
                Height = CellHeight,
                BorderThickness = new Thickness(1),
                HorizontalContentAlignment = HorizontalAlignment.Left,
                VerticalContentAlignment = VerticalAlignment.Center,
                FontFamily = new FontFamily("Comic Sans MS"),
                FontSize = 13,
                Text = text
            };
            SetLeft(label, left);
            SetTop(label, top);
            return (label);
        }
    }

}