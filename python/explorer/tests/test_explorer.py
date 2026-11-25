"""Tests for the DTree Explorer package: the bridge agrees with the library, the local
server answers, and the two page variants are built as intended."""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "dlist"))   # this repository's DList and DTree
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "dtree"))

from fractions import Fraction  # noqa: E402

from triordinal.dtree import DTree  # noqa: E402
from triordinal.dtree.euler import EulerTree  # noqa: E402
from triordinal.dtree.two_lists import DTree as DTree2  # noqa: E402

import build  # noqa: E402
from dtree_explorer import __main__ as app  # noqa: E402
from dtree_explorer import bridge  # noqa: E402


class TestBridge(unittest.TestCase):
    def test_examples_match_the_library(self):
        for name, text in build.examples().items():
            d = json.loads(bridge.encode(text))
            d2 = json.loads(bridge.encode(text, kind="dtree2"))
            self.assertEqual(d["errors"], [], name)
            t, t2 = DTree(), DTree2()
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    t.add_line(line)
                    t2.add_line(line)
            self.assertEqual(d["final"]["q1"], t.q1, name)
            self.assertEqual(d["final"]["q2"], t2.q2, name)            # Q2 read from the children = 2.x's Q2
            self.assertEqual(d2["final"]["q1"], t2.q1, name)
            self.assertEqual(d2["final"]["q2"], t2.q2, name)
            self.assertEqual(d["steps"][-1]["q1"], t.q1, name)

    def test_paper_examples(self):
        ex = build.examples()
        fig1 = json.loads(bridge.encode(ex["Paper, Figure 1"]))["final"]
        self.assertEqual(fig1["q1"], [str(i) for i in range(1, 13)])
        self.assertEqual(fig1["q2"], ["1", "2", "9", "12", "10", "11", "4", "5", "7", "8", "6", "3"])
        a = json.loads(bridge.encode(ex["Paper, Sec. 4.1, Case A: v before 6"]))["final"]
        self.assertEqual(a["q1"][4:7], ["5", "v", "6"])                  # v directly before 6 in Q1
        self.assertEqual(a["q2"][-3:], ["6", "v", "3"])                  # after 6's subtree in Q2
        for v in "ABC":
            files = [k for k in ex if f"Variant {v}:" in k][0]
            ops = [k for k in ex if f"Variant {v} with" in k][0]
            f1, f2 = json.loads(bridge.encode(ex[files]))["final"], json.loads(bridge.encode(ex[ops]))["final"]
            self.assertEqual((f1["q1"], f1["q2"]), (f2["q1"], f2["q2"]), v)

    def test_errors_and_limit(self):
        d = json.loads(bridge.encode("A: B\nX: Y\nA > Z\nnonsense\nB > C"))
        self.assertEqual([s["op"] for s in d["steps"]], ["A:B", "B>C"])
        self.assertEqual(len(d["errors"]), 3)
        big = "\n".join(["n0: n1"] + [f"n{i // 2}: n{i}" for i in range(2, 400)])
        d = json.loads(bridge.encode(big))
        self.assertFalse(d["stepwise"])
        self.assertNotIn("q1", d["steps"][0])
        self.assertEqual(len(d["final"]["q1"]), 400)


class TestEuler(unittest.TestCase):
    def test_examples_agree_with_dtree_and_the_library(self):
        for name, text in build.examples().items():
            for positions in bridge.POSITIONS:
                d = json.loads(bridge.encode(text))["final"]
                e = json.loads(bridge.encode(text, kind="euler", positions=positions))
                self.assertEqual(e["errors"], [], name)
                self.assertEqual((e["kind"], e["positions"], len(e["renumber"])), ("euler", positions, 1))
                f = e["final"]
                self.assertEqual(f["q1"], d["q1"], name)
                self.assertEqual(f["q2"], d["q2"], name)                # block ends from the right = Q2
                t = EulerTree(positions=positions)
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        t.add_line(line)
                self.assertEqual(f["q1"], t.q1, name)
                for u in f["q1"]:                                      # reach = inside the block
                    for v in f["q1"]:
                        inside = f["open"][u] < f["open"][v] < f["end"][u]
                        self.assertEqual(inside, t.can_reach(u, v), (name, u, v))

    def test_cells_and_positions(self):
        for positions, num in (("rational", Fraction), ("integer", int)):
            f = json.loads(bridge.encode("R: A; B\nA: C", kind="euler", positions=positions))["final"]
            self.assertEqual([c[0] for c in f["cells"]], ["R", "A", "C", ")A", "B", ")R"])
            vals = [num(c[1]) for c in f["cells"]]
            self.assertEqual(vals, sorted(vals))                       # positions increase along the list
            self.assertEqual(f["end"], {"R": 5, "A": 3, "C": 2, "B": 4})
            self.assertEqual(f["pos"]["A"], [f["cells"][1][1], f["cells"][3][1]])
            self.assertEqual(f["pos"]["C"][0], f["pos"]["C"][1])       # a leaf's block is its own cell
        d = json.loads(bridge.encode("R: A; B\nA: C", kind="dtree2", positions="integer"))["final"]
        self.assertTrue(all(int(p) >= 0 for v in d["pos"].values() for p in v))

    def test_steps_and_bad_options(self):
        d = json.loads(bridge.encode("A: B; C\nB: D", kind="euler"))
        self.assertEqual([s["new"] for s in d["steps"]], ["B", "C", "D"])
        self.assertEqual(d["steps"][0]["cells"], [["A", "0"], ["B", "1/2"], [")A", "1"]])
        with self.assertRaises(ValueError):
            bridge.encode("A: B", kind="q1")
        with self.assertRaises(ValueError):
            bridge.encode("A: B", positions="decimal")


class TestDTree3(unittest.TestCase):
    def test_blocks_end_before_the_delimiter(self):
        for name, text in build.examples().items():
            for positions in bridge.POSITIONS:
                d = json.loads(bridge.encode(text, positions=positions))
                self.assertEqual((d["kind"], len(d["renumber"])), ("dtree", 1))
                f = d["final"]
                t = DTree(positions=positions)
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        t.add_line(line)
                self.assertEqual([c[0] for c in f["cells"]], t.q1, name)       # Q1 as stored, no closing cells
                for u in f["q1"]:
                    d_ = f["delim"][u]
                    self.assertEqual(f["end"][u] + 1, f["open"][d_] if d_ != "]" else len(f["cells"]), (name, u))
                    for v in f["q1"]:
                        inside = f["open"][u] < f["open"][v] <= f["end"][u]
                        self.assertEqual(inside, t.can_reach(u, v), (name, u, v))

    def test_delimiters(self):
        f = json.loads(bridge.encode("R: A; B\nA: C"))["final"]
        self.assertEqual(f["cells"][0][0], "R")
        self.assertEqual(f["delim"], {"R": "]", "A": "B", "C": "B", "B": "]"})   # C is A's last child: A's delimiter
        self.assertEqual(f["pos"]["R"][1], "]")
        self.assertEqual(f["run"], {"R": "R", "A": "A", "C": "A", "B": "B"})     # C is A's only child: A's run


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = app.serve(0)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}/"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_page_info_encode(self):
        html = urllib.request.urlopen(self.url).read().decode()
        self.assertIn("<title>DTree Explorer</title>", html)
        info = json.loads(urllib.request.urlopen(self.url + "api/info").read())
        self.assertIn("dtree", info)
        req = urllib.request.Request(self.url + "api/encode", data="A: B; C\nB: D".encode(), method="POST")
        d = json.loads(urllib.request.urlopen(req).read())
        self.assertEqual(d["final"]["q1"], ["A", "B", "D", "C"])
        self.assertEqual((d["kind"], d["positions"]), ("dtree", "rational"))
        req = urllib.request.Request(self.url + "api/encode?kind=euler&positions=integer", data="A: B; C\nB: D".encode(), method="POST")
        d = json.loads(urllib.request.urlopen(req).read())
        self.assertEqual((d["kind"], d["positions"]), ("euler", "integer"))
        self.assertEqual([c[0] for c in d["final"]["cells"]], ["A", "B", "D", ")B", "C", ")A"])
        req = urllib.request.Request(self.url + "api/encode?kind=nope", data=b"A: B", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)

    def test_foreign_host_refused(self):
        req = urllib.request.Request(self.url + "api/info", headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)


class TestPages(unittest.TestCase):
    def test_variants(self):
        plain, site = build.page(), build.page(build.SITE["counter"], build.SITE["privacy"])
        for html in (plain, site):
            self.assertNotRegex(html, r"__[A-Z_]+__")
            self.assertNotIn("googletagmanager", html)                     # no Google Analytics anywhere
            self.assertIn("class EulerTree", html)                          # the fallback copy holds euler.py
            self.assertIn("DTree 2.x: a single-rooted", html)              # ... and two_lists.py
        self.assertNotIn(build.SITE["counter"], plain)                    # package copy: no visit counting
        self.assertIn(build.SITE["counter"], site)

    def test_save(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "explorer.html")
            self.assertEqual(app.main(["--save", path]), 0)
            with open(path, encoding="utf-8") as fh:
                self.assertIn("DTree Explorer", fh.read())


if __name__ == "__main__":
    unittest.main()
